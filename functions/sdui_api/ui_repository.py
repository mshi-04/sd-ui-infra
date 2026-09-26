from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from azure.core.exceptions import AzureError, ServiceRequestError, ServiceResponseError
from azure.core.pipeline.transport import RequestsTransport
from azure.cosmos import ContainerProxy, CosmosClient
from azure.cosmos.exceptions import CosmosClientTimeoutError, CosmosHttpResponseError, CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

from constants import Settings
from dependency_errors import DependencyFailureError, DependencyUnavailableError
from models import AccountProfile, UiDefinition

LATEST_DEFINITION_QUERY = "SELECT TOP 1 * FROM c WHERE c.surface = @surface ORDER BY c.version DESC"

COSMOS_DEPENDENCY = "cosmos"
COSMOS_OPERATION_TIMEOUT_SECONDS = 4
COSMOS_CONNECT_TIMEOUT_SECONDS = 2
COSMOS_READ_TIMEOUT_SECONDS = 2
COSMOS_RETRY_TOTAL = 1
COSMOS_RETRY_BACKOFF_MAX_SECONDS = 1
TRANSIENT_STATUS_CODES = frozenset({408, 429, 503, 504})
TRANSIENT_ERROR_TYPES = (CosmosClientTimeoutError, ServiceRequestError, ServiceResponseError)


@lru_cache(maxsize=1)
def _client(endpoint: str) -> CosmosClient:
    return CosmosClient(
        endpoint,
        credential=DefaultAzureCredential(),
        transport=RequestsTransport(read_timeout=COSMOS_READ_TIMEOUT_SECONDS),
        timeout=COSMOS_OPERATION_TIMEOUT_SECONDS,
        connection_timeout=COSMOS_CONNECT_TIMEOUT_SECONDS,
        retry_total=COSMOS_RETRY_TOTAL,
        retry_backoff_max=COSMOS_RETRY_BACKOFF_MAX_SECONDS,
        # Single-region account: with discovery on, the SDK re-sends a read that got 408 immediately, up to 120 times.
        enable_endpoint_discovery=False,
    )


def _container(settings: Settings, container_name: str) -> ContainerProxy:
    database = _client(settings.cosmos_endpoint).get_database_client(settings.cosmos_database)
    return database.get_container_client(container_name)


def _is_transient(error: AzureError) -> bool:
    if isinstance(error, CosmosHttpResponseError):
        return error.status_code in TRANSIENT_STATUS_CODES
    return isinstance(error, TRANSIENT_ERROR_TYPES)


def _describe(error: AzureError) -> str:
    if isinstance(error, CosmosHttpResponseError):
        return f"{type(error).__name__} status={error.status_code} sub_status={error.sub_status}"
    return type(error).__name__


class _QueryPageRecorder:
    def __init__(self) -> None:
        self.received = False

    def __call__(self, headers: Mapping[str, Any], result: Any) -> None:
        # query_items also passes its not-yet-iterated pager to the hook; only page bodies are mappings.
        if isinstance(result, Mapping):
            self.received = True


@contextmanager
def _classified_failures(container_name: str) -> Iterator[None]:
    try:
        yield
    except AzureError as error:
        failure = DependencyUnavailableError if _is_transient(error) else DependencyFailureError
        raise failure(_dependency(container_name), _describe(error)) from error


def _dependency(container_name: str) -> str:
    return f"{COSMOS_DEPENDENCY}.{container_name}"


def fetch_latest_definition(settings: Settings, surface: str) -> UiDefinition | None:
    pages = _QueryPageRecorder()
    with _classified_failures(settings.ui_definitions_container):
        container = _container(settings, settings.ui_definitions_container)
        documents = list(
            container.query_items(
                query=LATEST_DEFINITION_QUERY,
                parameters=[{"name": "@surface", "value": surface}],
                partition_key=surface,
                timeout=COSMOS_OPERATION_TIMEOUT_SECONDS,
                response_hook=pages,
            )
        )
    if not documents:
        # azure-cosmos 4.9.0 ends the iteration without error when its query-level retry (e.g. after exhausted
        # throttling retries) re-enters the first page fetch, so an empty result counts only with a response page.
        if not pages.received:
            raise DependencyUnavailableError(_dependency(settings.ui_definitions_container), "query_without_response")
        return None
    return UiDefinition.from_document(documents[0])


def fetch_profile(settings: Settings, user_id: str) -> AccountProfile:
    with _classified_failures(settings.account_profiles_container):
        container = _container(settings, settings.account_profiles_container)
        try:
            document = container.read_item(item=user_id, partition_key=user_id, timeout=COSMOS_OPERATION_TIMEOUT_SECONDS)
        except CosmosResourceNotFoundError:
            return AccountProfile.empty(user_id)
    return AccountProfile.from_document(document)
