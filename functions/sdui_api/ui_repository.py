from functools import lru_cache

from azure.cosmos import ContainerProxy, CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

from constants import Settings
from models import AccountProfile, UiDefinition

LATEST_DEFINITION_QUERY = "SELECT TOP 1 * FROM c WHERE c.surface = @surface ORDER BY c.version DESC"


@lru_cache(maxsize=1)
def _client(endpoint: str) -> CosmosClient:
    return CosmosClient(endpoint, credential=DefaultAzureCredential())


def _container(settings: Settings, container_name: str) -> ContainerProxy:
    database = _client(settings.cosmos_endpoint).get_database_client(settings.cosmos_database)
    return database.get_container_client(container_name)


def fetch_latest_definition(settings: Settings, surface: str) -> UiDefinition | None:
    container = _container(settings, settings.ui_definitions_container)
    documents = list(
        container.query_items(
            query=LATEST_DEFINITION_QUERY,
            parameters=[{"name": "@surface", "value": surface}],
            partition_key=surface,
        )
    )
    if not documents:
        return None
    return UiDefinition.from_document(documents[0])


def fetch_profile(settings: Settings, user_id: str) -> AccountProfile:
    container = _container(settings, settings.account_profiles_container)
    try:
        document = container.read_item(item=user_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return AccountProfile.empty(user_id)
    return AccountProfile.from_document(document)
