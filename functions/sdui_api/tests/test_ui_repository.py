from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from azure.core.exceptions import ClientAuthenticationError, DecodeError, ServiceRequestError, ServiceResponseError
from azure.cosmos.exceptions import CosmosClientTimeoutError, CosmosHttpResponseError, CosmosResourceNotFoundError
from azure.identity import CredentialUnavailableError
from conftest import query_returning

import ui_repository
from dependency_errors import DependencyFailureError, DependencyUnavailableError
from models import AccountProfile
from settings import Settings

USER_ID = "missing-user"
DEFINITION_DOCUMENT = {"surface": "dashboard", "version": "2026-06-01", "revision": "a1b2c3", "components": []}

TRANSIENT_FAILURES = [
    pytest.param(ServiceRequestError(f"cannot connect for {USER_ID}"), id="connection"),
    pytest.param(ServiceResponseError(f"connection reset for {USER_ID}"), id="response"),
    pytest.param(CosmosClientTimeoutError(), id="client-timeout"),
    pytest.param(CosmosHttpResponseError(status_code=408, message=f"timeout for {USER_ID}"), id="status-408"),
    pytest.param(CosmosHttpResponseError(status_code=429, message=f"throttled for {USER_ID}"), id="status-429"),
    pytest.param(CosmosHttpResponseError(status_code=503, message=f"unavailable for {USER_ID}"), id="status-503"),
    pytest.param(CosmosHttpResponseError(status_code=504, message=f"gateway timeout for {USER_ID}"), id="status-504"),
]

PERSISTENT_FAILURES = [
    pytest.param(CosmosHttpResponseError(status_code=401, message=f"bad token for {USER_ID}"), id="status-401"),
    pytest.param(CosmosHttpResponseError(status_code=403, message=f"rbac denied for {USER_ID}"), id="status-403"),
    pytest.param(CosmosHttpResponseError(status_code=500, message=f"server error for {USER_ID}"), id="status-500"),
    pytest.param(ClientAuthenticationError(f"token request failed for {USER_ID}"), id="credential"),
    pytest.param(CredentialUnavailableError(f"no identity for {USER_ID}"), id="credential-unavailable"),
    pytest.param(DecodeError(f"invalid json for {USER_ID}"), id="decode"),
]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        tenant_id="tenant",
        api_client_id="audience",
        required_scope="UiSchema.Read",
        cosmos_endpoint="https://example.invalid/",
        cosmos_database="test-db",
        ui_definitions_container="ui-definitions",
        account_profiles_container="account-profiles",
        cache_max_age_seconds=60,
        role_entitlements={},
    )


@pytest.fixture
def container(monkeypatch: pytest.MonkeyPatch) -> Mock:
    container = Mock()
    monkeypatch.setattr(ui_repository, "_container", Mock(return_value=container))
    return container


@pytest.fixture
def cosmos_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[Mock]:
    client = Mock()
    monkeypatch.setattr(ui_repository, "CosmosClient", client)
    monkeypatch.setattr(ui_repository, "DefaultAzureCredential", Mock(return_value="credential"))
    ui_repository._client.cache_clear()
    yield client
    ui_repository._client.cache_clear()


def test_missing_cosmos_profile_becomes_empty_profile(container: Mock, settings: Settings) -> None:
    container.read_item.side_effect = CosmosResourceNotFoundError(message="profile missing")

    profile = ui_repository.fetch_profile(settings, USER_ID)

    assert profile == AccountProfile.empty(USER_ID)
    container.read_item.assert_called_once_with(
        item=USER_ID, partition_key=USER_ID, timeout=ui_repository.COSMOS_OPERATION_TIMEOUT_SECONDS
    )


def test_latest_definition_query_is_bounded_and_scoped_to_surface(container: Mock, settings: Settings) -> None:
    container.query_items.side_effect = query_returning(DEFINITION_DOCUMENT)

    definition = ui_repository.fetch_latest_definition(settings, "dashboard")

    assert definition is not None and definition.revision == "a1b2c3"
    kwargs = container.query_items.call_args.kwargs
    assert kwargs["query"] == "SELECT TOP 1 * FROM c WHERE c.surface = @surface ORDER BY c.version DESC"
    assert kwargs["parameters"] == [{"name": "@surface", "value": "dashboard"}]
    assert kwargs["partition_key"] == "dashboard"
    assert kwargs["timeout"] == ui_repository.COSMOS_OPERATION_TIMEOUT_SECONDS


def test_empty_query_page_means_unknown_surface(container: Mock, settings: Settings) -> None:
    container.query_items.side_effect = query_returning()

    assert ui_repository.fetch_latest_definition(settings, "unknown") is None


def _query_reporting_only_the_pager(**kwargs: object) -> list[object]:
    pager: list[object] = []
    kwargs["response_hook"]({}, pager)
    return pager


@pytest.mark.parametrize(
    "query_items",
    [
        pytest.param(lambda **kwargs: [], id="no-hook-call"),
        pytest.param(_query_reporting_only_the_pager, id="pager-only"),
    ],
)
def test_empty_query_without_response_page_is_not_treated_as_unknown_surface(
    query_items: object, container: Mock, settings: Settings
) -> None:
    container.query_items.side_effect = query_items

    with pytest.raises(DependencyUnavailableError) as error:
        ui_repository.fetch_latest_definition(settings, "dashboard")

    assert error.value.dependency == "cosmos.ui-definitions"
    assert error.value.detail == "query_without_response"


@pytest.mark.parametrize("failure", TRANSIENT_FAILURES)
def test_transient_definition_failures_are_unavailable_dependency(
    failure: Exception, container: Mock, settings: Settings
) -> None:
    container.query_items.side_effect = failure

    with pytest.raises(DependencyUnavailableError) as error:
        ui_repository.fetch_latest_definition(settings, "dashboard")

    assert error.value.dependency == "cosmos.ui-definitions"
    assert error.value.__cause__ is failure
    assert USER_ID not in str(error.value)


@pytest.mark.parametrize("failure", [*PERSISTENT_FAILURES, pytest.param(CosmosResourceNotFoundError(message="gone"), id="404")])
def test_persistent_definition_failures_are_failed_dependency(failure: Exception, container: Mock, settings: Settings) -> None:
    container.query_items.side_effect = failure

    with pytest.raises(DependencyFailureError) as error:
        ui_repository.fetch_latest_definition(settings, "dashboard")

    assert error.value.dependency == "cosmos.ui-definitions"
    assert USER_ID not in str(error.value)


@pytest.mark.parametrize(
    ("failure", "classified_as"),
    [
        pytest.param(ServiceRequestError(f"cannot connect for {USER_ID}"), DependencyUnavailableError, id="connection"),
        pytest.param(
            CosmosHttpResponseError(status_code=429, message=f"throttled for {USER_ID}"), DependencyUnavailableError, id="429"
        ),
        pytest.param(
            CosmosHttpResponseError(status_code=403, message=f"rbac denied for {USER_ID}"), DependencyFailureError, id="403"
        ),
        pytest.param(ClientAuthenticationError(f"token request failed for {USER_ID}"), DependencyFailureError, id="credential"),
    ],
)
def test_profile_lookup_failures_are_not_treated_as_missing_profile(
    failure: Exception, classified_as: type[Exception], container: Mock, settings: Settings
) -> None:
    container.read_item.side_effect = failure

    with pytest.raises(classified_as) as error:
        ui_repository.fetch_profile(settings, USER_ID)

    assert error.value.dependency == "cosmos.account-profiles"
    assert USER_ID not in str(error.value)


def test_http_failure_detail_keeps_only_type_and_status(container: Mock, settings: Settings) -> None:
    container.read_item.side_effect = CosmosHttpResponseError(status_code=403, message=f"principal cannot read docs/{USER_ID}")

    with pytest.raises(DependencyFailureError) as error:
        ui_repository.fetch_profile(settings, USER_ID)

    assert error.value.detail == "CosmosHttpResponseError status=403 sub_status=None"


def test_client_construction_failure_is_classified(cosmos_client: Mock, settings: Settings) -> None:
    cosmos_client.side_effect = CosmosClientTimeoutError()

    with pytest.raises(DependencyUnavailableError) as error:
        ui_repository.fetch_latest_definition(settings, "dashboard")

    assert error.value.detail == "CosmosClientTimeoutError"


def test_cosmos_client_is_bounded_by_timeouts_and_limited_retries(cosmos_client: Mock) -> None:
    ui_repository._client("https://example.invalid/")

    cosmos_client.assert_called_once()
    args, kwargs = cosmos_client.call_args
    assert args == ("https://example.invalid/",)
    assert kwargs["credential"] == "credential"
    assert kwargs["timeout"] == ui_repository.COSMOS_OPERATION_TIMEOUT_SECONDS == 4
    assert kwargs["connection_timeout"] == ui_repository.COSMOS_CONNECT_TIMEOUT_SECONDS == 2
    assert kwargs["transport"].connection_config.read_timeout == ui_repository.COSMOS_READ_TIMEOUT_SECONDS == 2
    assert kwargs["retry_total"] == ui_repository.COSMOS_RETRY_TOTAL == 1
    assert kwargs["retry_backoff_max"] == ui_repository.COSMOS_RETRY_BACKOFF_MAX_SECONDS == 1
    assert kwargs["enable_endpoint_discovery"] is False
