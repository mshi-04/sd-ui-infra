import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_SCOPE = "UiSchema.Read"
DEFAULT_CACHE_MAX_AGE_SECONDS = 60
SUBJECT_MASK_LENGTH = 12


class SettingsError(Exception):
    def __init__(self, variable: str, problem: str) -> None:
        super().__init__(f"{problem} {variable}")
        self.variable = variable
        self.problem = problem


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
    roles = json.loads(document)
    if not isinstance(roles, dict) or not all(_is_string_list(entitlements) for entitlements in roles.values()):
        raise ValueError("role entitlements must map each role to a list of entitlement names")
    return {role: frozenset(entitlements) for role, entitlements in roles.items()}


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings(
        tenant_id=_required("ENTRA_TENANT_ID"),
        api_client_id=_required("ENTRA_API_CLIENT_ID"),
        required_scope=os.environ.get("REQUIRED_SCOPE", DEFAULT_SCOPE),
        cosmos_endpoint=_required("COSMOS_ENDPOINT"),
        cosmos_database=_required("COSMOS_DATABASE"),
        ui_definitions_container=_required("UI_DEFINITIONS_CONTAINER"),
        account_profiles_container=_required("ACCOUNT_PROFILES_CONTAINER"),
        cache_max_age_seconds=_parsed("UI_CACHE_MAX_AGE_SECONDS", int, str(DEFAULT_CACHE_MAX_AGE_SECONDS)),
        role_entitlements=_parsed("ROLE_ENTITLEMENTS", parse_role_entitlements, "{}"),
    )


def _required(name: str) -> str:
    try:
        return os.environ[name]
    except KeyError:
        raise SettingsError(name, "missing") from None


def _parsed[T](name: str, parse: Callable[[str], T], default: str) -> T:
    try:
        return parse(os.environ.get(name, default))
    except ValueError:
        # The parser messages quote the raw value, so the cause is dropped rather than chained.
        raise SettingsError(name, "invalid") from None
