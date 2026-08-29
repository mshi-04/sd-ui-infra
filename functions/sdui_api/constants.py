import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_SCOPE = "UiSchema.Read"
DEFAULT_CACHE_MAX_AGE_SECONDS = 60
SUBJECT_MASK_LENGTH = 12


@dataclass(frozen=True)
class Settings:
    tenant_id: str
    api_client_id: str
    required_scope: str
    cosmos_endpoint: str
    cosmos_database: str
    ui_definitions_container: str
    account_profiles_container: str
    cache_max_age_seconds: int
    role_entitlements: Mapping[str, frozenset[str]]

    @property
    def issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def jwks_uri(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"


def parse_role_entitlements(document: str) -> Mapping[str, frozenset[str]]:
    return {role: frozenset(entitlements) for role, entitlements in json.loads(document).items()}


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings(
        tenant_id=os.environ["ENTRA_TENANT_ID"],
        api_client_id=os.environ["ENTRA_API_CLIENT_ID"],
        required_scope=os.environ.get("REQUIRED_SCOPE", DEFAULT_SCOPE),
        cosmos_endpoint=os.environ["COSMOS_ENDPOINT"],
        cosmos_database=os.environ["COSMOS_DATABASE"],
        ui_definitions_container=os.environ["UI_DEFINITIONS_CONTAINER"],
        account_profiles_container=os.environ["ACCOUNT_PROFILES_CONTAINER"],
        cache_max_age_seconds=int(os.environ.get("UI_CACHE_MAX_AGE_SECONDS", DEFAULT_CACHE_MAX_AGE_SECONDS)),
        role_entitlements=parse_role_entitlements(os.environ.get("ROLE_ENTITLEMENTS", "{}")),
    )
