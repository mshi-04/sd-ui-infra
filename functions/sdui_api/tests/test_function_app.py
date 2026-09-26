import json
import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any
from unittest.mock import Mock

import azure.functions as func
import pytest
from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError
from azure.cosmos.exceptions import CosmosClientTimeoutError, CosmosHttpResponseError
from conftest import AUDIENCE, ISSUER, REQUIRED_SCOPE, SUBJECT, query_returning
from jwt.exceptions import PyJWKClientConnectionError

import function_app
import ui_repository
from constants import Settings
from models import AccountProfile, UiDefinition


@pytest.fixture
def settings() -> Settings:
    return Settings(
        tenant_id=ISSUER.split("/")[3],
        api_client_id=AUDIENCE,
        required_scope=REQUIRED_SCOPE,
        cosmos_endpoint="https://example.invalid/",
        cosmos_database="test-db",
        ui_definitions_container="ui-definitions",
        account_profiles_container="account-profiles",
        cache_max_age_seconds=60,
        role_entitlements={"BillingViewer": frozenset({"billing.read"})},
    )


@pytest.fixture
def definition() -> UiDefinition:
    return UiDefinition.from_document(
        {
            "surface": "dashboard",
            "version": "2026-06-01",
            "revision": "a1b2c3",
            "components": [
                {"id": "usage-summary", "type": "Card", "props": {"title": "Usage"}},
                {
                    "id": "billing-summary",
                    "type": "Card",
                    "props": {"title": "Billing"},
                    "requiredEntitlements": ["billing.read"],
                },
            ],
        }
    )


@pytest.fixture
def entry(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, definition: UiDefinition, key_resolver: Callable[[str], object]
) -> tuple[Mock, Mock]:
    fetch_definition = Mock(return_value=definition)
    fetch_profile = Mock(return_value=AccountProfile.empty(SUBJECT))
    monkeypatch.setattr(function_app, "load_settings", lambda: settings)
    monkeypatch.setattr(function_app, "jwks_key_resolver", lambda uri: key_resolver)
    monkeypatch.setattr(function_app, "fetch_latest_definition", fetch_definition)
    monkeypatch.setattr(function_app, "fetch_profile", fetch_profile)
    return fetch_definition, fetch_profile


def _request(token: str | None, *, surface: str = "dashboard", if_none_match: str | None = None) -> func.HttpRequest:
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if if_none_match is not None:
        headers["If-None-Match"] = if_none_match
    return func.HttpRequest(
        method="GET",
        url=f"https://example.invalid/api/ui/{surface}",
        headers=headers,
        body=b"",
        route_params={"surface": surface},
    )


def _payload(response: func.HttpResponse) -> dict[str, Any]:
    return json.loads(response.get_body())


def _component_ids(response: func.HttpResponse) -> list[str]:
    return [component["id"] for component in _payload(response)["components"]]


@pytest.mark.parametrize("cache_max_age_seconds", [60, 137])
def test_get_ui_schema_returns_resolved_payload_and_cache_headers(
    cache_max_age_seconds: int,
    issue_token: Callable[..., str],
    entry: tuple[Mock, Mock],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_definition, fetch_profile = entry
    settings = replace(settings, cache_max_age_seconds=cache_max_age_seconds)
    monkeypatch.setattr(function_app, "load_settings", lambda: settings)

    response = function_app.get_ui_schema(_request(issue_token()))

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert _payload(response) == {
        "surface": "dashboard",
        "version": "2026-06-01",
        "revision": "a1b2c3",
        "theme": "light",
        "density": "comfortable",
        "components": [
            {"id": "usage-summary", "type": "Card", "props": {"title": "Usage"}, "children": []},
            {"id": "billing-summary", "type": "Card", "props": {"title": "Billing"}, "children": []},
        ],
    }
    assert response.headers["ETag"].startswith('"') and response.headers["ETag"].endswith('"')
    assert response.headers["Cache-Control"] == f"private, max-age={cache_max_age_seconds}"
    fetch_definition.assert_called_once_with(settings, "dashboard")
    fetch_profile.assert_called_once_with(settings, SUBJECT)


def test_matching_etag_returns_empty_304_with_cache_headers(issue_token: Callable[..., str], entry: tuple[Mock, Mock]) -> None:
    token = issue_token()
    current = function_app.get_ui_schema(_request(token))

    response = function_app.get_ui_schema(_request(token, if_none_match=current.headers["ETag"]))

    assert response.status_code == 304
    assert response.get_body() == b""
    assert response.headers["ETag"] == current.headers["ETag"]
    assert response.headers["Cache-Control"] == current.headers["Cache-Control"]


def test_mismatched_etag_returns_current_payload(issue_token: Callable[..., str], entry: tuple[Mock, Mock]) -> None:
    response = function_app.get_ui_schema(_request(issue_token(), if_none_match='"outdated"'))

    assert response.status_code == 200
    assert _component_ids(response) == ["usage-summary", "billing-summary"]
    assert response.headers["ETag"] != '"outdated"'


@pytest.mark.parametrize("conditional_etag", ["W/{etag}", '{etag}, "other"', "*"])
def test_conditional_etag_uses_current_exact_string_comparison(
    conditional_etag: str, issue_token: Callable[..., str], entry: tuple[Mock, Mock]
) -> None:
    token = issue_token()
    current = function_app.get_ui_schema(_request(token))

    response = function_app.get_ui_schema(_request(token, if_none_match=conditional_etag.format(etag=current.headers["ETag"])))

    assert response.status_code == 200
    assert _payload(response) == _payload(current)
    assert response.headers["ETag"] == current.headers["ETag"]


@pytest.mark.parametrize("authorization", [None, "invalid-token"])
def test_missing_or_invalid_auth_returns_generic_401_without_database_access(
    authorization: str | None, entry: tuple[Mock, Mock]
) -> None:
    fetch_definition, fetch_profile = entry

    response = function_app.get_ui_schema(_request(authorization))

    assert response.status_code == 401
    assert response.mimetype == "application/json"
    assert _payload(response) == {"error": {"code": "unauthorized"}}
    fetch_definition.assert_not_called()
    fetch_profile.assert_not_called()


def test_unknown_surface_returns_404_without_profile_lookup(
    issue_token: Callable[..., str], entry: tuple[Mock, Mock], settings: Settings
) -> None:
    fetch_definition, fetch_profile = entry
    fetch_definition.return_value = None

    response = function_app.get_ui_schema(_request(issue_token(), surface="unknown"))

    assert response.status_code == 404
    assert response.mimetype == "application/json"
    assert _payload(response) == {"error": {"code": "surface_not_found"}}
    fetch_definition.assert_called_once_with(settings, "unknown")
    fetch_profile.assert_not_called()


def test_missing_profile_resolves_with_empty_defaults(issue_token: Callable[..., str], entry: tuple[Mock, Mock]) -> None:
    _, fetch_profile = entry
    fetch_profile.return_value = AccountProfile.empty(SUBJECT)

    response = function_app.get_ui_schema(_request(issue_token(roles=[])))

    assert response.status_code == 200
    assert _component_ids(response) == ["usage-summary"]
    assert _payload(response)["theme"] == "light"
    assert _payload(response)["density"] == "comfortable"


def test_changed_entitlements_change_payload_and_etag_and_reject_old_etag(
    issue_token: Callable[..., str], entry: tuple[Mock, Mock]
) -> None:
    _, fetch_profile = entry
    token = issue_token(roles=[])
    fetch_profile.return_value = AccountProfile.empty(SUBJECT)
    original = function_app.get_ui_schema(_request(token))
    fetch_profile.return_value = AccountProfile(user_id=SUBJECT, entitlements=frozenset({"billing.read"}))

    changed = function_app.get_ui_schema(_request(token, if_none_match=original.headers["ETag"]))

    assert original.status_code == changed.status_code == 200
    assert _component_ids(original) == ["usage-summary"]
    assert _component_ids(changed) == ["usage-summary", "billing-summary"]
    assert _payload(original)["revision"] == _payload(changed)["revision"]
    assert original.headers["ETag"] != changed.headers["ETag"]


@pytest.fixture
def containers(monkeypatch: pytest.MonkeyPatch, settings: Settings, key_resolver: Callable[[str], object]) -> dict[str, Mock]:
    definitions = Mock()
    definitions.query_items.side_effect = query_returning({"surface": "dashboard", "version": "2026-06-01", "revision": "a1b2c3"})
    profiles = Mock()
    profiles.read_item.return_value = {"id": SUBJECT, "userId": SUBJECT}
    by_name = {settings.ui_definitions_container: definitions, settings.account_profiles_container: profiles}
    monkeypatch.setattr(function_app, "load_settings", lambda: settings)
    monkeypatch.setattr(function_app, "jwks_key_resolver", lambda uri: key_resolver)
    monkeypatch.setattr(ui_repository, "_container", lambda settings, name: by_name[name])
    return by_name


@pytest.fixture
def external_calls(monkeypatch: pytest.MonkeyPatch, settings_environment: pytest.MonkeyPatch) -> dict[str, Mock]:
    calls = {name: Mock() for name in ["jwks_key_resolver", "fetch_latest_definition", "fetch_profile"]}
    for name, mock in calls.items():
        monkeypatch.setattr(function_app, name, mock)
    return calls


def _assert_error(response: func.HttpResponse, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    assert response.mimetype == "application/json"
    assert _payload(response) == {"error": {"code": code}}
    assert "ETag" not in response.headers
    assert "Cache-Control" not in response.headers


def test_repository_path_resolves_payload(issue_token: Callable[..., str], containers: dict[str, Mock]) -> None:
    response = function_app.get_ui_schema(_request(issue_token()))

    assert response.status_code == 200
    assert _payload(response)["revision"] == "a1b2c3"


def test_jwks_connection_failure_returns_503_without_database_access(
    issue_token: Callable[..., str],
    entry: tuple[Mock, Mock],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fetch_definition, fetch_profile = entry
    token = issue_token()

    def unreachable_resolver(token: str) -> object:
        raise PyJWKClientConnectionError(f"jwks unreachable for {token}")

    monkeypatch.setattr(function_app, "jwks_key_resolver", lambda uri: unreachable_resolver)

    with caplog.at_level(logging.INFO):
        response = function_app.get_ui_schema(_request(token))

    _assert_error(response, 503, "service_unavailable")
    fetch_definition.assert_not_called()
    fetch_profile.assert_not_called()
    assert "dependency=jwks" in caplog.text
    assert token not in caplog.text


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(ServiceRequestError("cannot connect"), id="connection"),
        pytest.param(CosmosClientTimeoutError(), id="client-timeout"),
        pytest.param(CosmosHttpResponseError(status_code=429, message="throttled"), id="status-429"),
        pytest.param(CosmosHttpResponseError(status_code=503, message="unavailable"), id="status-503"),
    ],
)
def test_transient_definition_lookup_failure_returns_503_instead_of_404(
    failure: Exception, issue_token: Callable[..., str], containers: dict[str, Mock], settings: Settings
) -> None:
    containers[settings.ui_definitions_container].query_items.side_effect = failure

    response = function_app.get_ui_schema(_request(issue_token()))

    _assert_error(response, 503, "service_unavailable")
    containers[settings.account_profiles_container].read_item.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(CosmosHttpResponseError(status_code=403, message="rbac denied"), id="status-403"),
        pytest.param(ClientAuthenticationError("no managed identity"), id="credential"),
    ],
)
def test_persistent_definition_lookup_failure_returns_500(
    failure: Exception, issue_token: Callable[..., str], containers: dict[str, Mock], settings: Settings
) -> None:
    containers[settings.ui_definitions_container].query_items.side_effect = failure

    response = function_app.get_ui_schema(_request(issue_token()))

    _assert_error(response, 500, "internal_error")


@pytest.mark.parametrize(
    ("failure", "status_code", "code"),
    [
        pytest.param(CosmosClientTimeoutError(), 503, "service_unavailable", id="client-timeout"),
        pytest.param(
            CosmosHttpResponseError(status_code=403, message=f"rbac denied for docs/{SUBJECT}"),
            500,
            "internal_error",
            id="status-403",
        ),
    ],
)
def test_profile_lookup_failure_is_not_served_as_empty_profile(
    failure: Exception,
    status_code: int,
    code: str,
    issue_token: Callable[..., str],
    containers: dict[str, Mock],
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    containers[settings.account_profiles_container].read_item.side_effect = failure

    with caplog.at_level(logging.INFO):
        response = function_app.get_ui_schema(_request(issue_token()))

    _assert_error(response, status_code, code)
    assert "dependency=cosmos.account-profiles" in caplog.text
    assert SUBJECT not in caplog.text


def test_invalid_stored_definition_returns_500(
    issue_token: Callable[..., str], containers: dict[str, Mock], settings: Settings
) -> None:
    containers[settings.ui_definitions_container].query_items.side_effect = query_returning({"surface": "dashboard"})

    response = function_app.get_ui_schema(_request(issue_token()))

    _assert_error(response, 500, "internal_error")


def test_unexpected_resolution_failure_returns_500(
    issue_token: Callable[..., str], entry: tuple[Mock, Mock], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(function_app, "resolve", Mock(side_effect=RuntimeError("resolver bug")))

    response = function_app.get_ui_schema(_request(issue_token()))

    _assert_error(response, 500, "internal_error")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        pytest.param("ENTRA_TENANT_ID", None, id="missing-variable"),
        pytest.param("UI_CACHE_MAX_AGE_SECONDS", "sixty-seconds", id="invalid-integer"),
        pytest.param("ROLE_ENTITLEMENTS", "{not-json-roles", id="invalid-role-json"),
        pytest.param("ROLE_ENTITLEMENTS", '{"BillingViewer": "billing.read"}', id="invalid-role-structure"),
    ],
)
def test_settings_failure_returns_500_without_external_calls(
    name: str,
    value: str | None,
    issue_token: Callable[..., str],
    external_calls: dict[str, Mock],
    settings_environment: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    if value is None:
        settings_environment.delenv(name)
    else:
        settings_environment.setenv(name, value)

    with caplog.at_level(logging.INFO):
        response = function_app.get_ui_schema(_request(issue_token()))

    _assert_error(response, 500, "internal_error")
    for external_call in external_calls.values():
        external_call.assert_not_called()
    assert f"variable={name}" in caplog.text
    if value is not None:
        assert value not in caplog.text
