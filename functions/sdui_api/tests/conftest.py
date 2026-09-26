import datetime as dt
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from constants import load_settings

ISSUER = "https://login.microsoftonline.com/11111111-1111-1111-1111-111111111111/v2.0"
AUDIENCE = "22222222-2222-2222-2222-222222222222"
SUBJECT = "33333333-3333-3333-3333-333333333333"
REQUIRED_SCOPE = "UiSchema.Read"

REQUIRED_ENVIRONMENT = {
    "ENTRA_TENANT_ID": ISSUER.split("/")[3],
    "ENTRA_API_CLIENT_ID": AUDIENCE,
    "COSMOS_ENDPOINT": "https://example.invalid/",
    "COSMOS_DATABASE": "test-db",
    "UI_DEFINITIONS_CONTAINER": "ui-definitions",
    "ACCOUNT_PROFILES_CONTAINER": "account-profiles",
}
OPTIONAL_ENVIRONMENT = ["REQUIRED_SCOPE", "UI_CACHE_MAX_AGE_SECONDS", "ROLE_ENTITLEMENTS"]


@pytest.fixture(scope="session")
def private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def key_resolver(private_key: rsa.RSAPrivateKey):
    public_key = private_key.public_key()

    def resolve(token: str) -> Any:
        return public_key

    return resolve


@pytest.fixture
def issue_token(private_key: rsa.RSAPrivateKey):
    def issue(**overrides: Any) -> str:
        now = dt.datetime.now(tz=dt.UTC)
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "oid": SUBJECT,
            "scp": REQUIRED_SCOPE,
            "roles": ["BillingViewer"],
            "nbf": now,
            "exp": now + dt.timedelta(minutes=10),
        }
        claims.update(overrides)
        present = {name: value for name, value in claims.items() if value is not None}
        return jwt.encode(present, private_key, algorithm="RS256")

    return issue


@pytest.fixture
def settings_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    for name in [*REQUIRED_ENVIRONMENT, *OPTIONAL_ENVIRONMENT]:
        monkeypatch.delenv(name, raising=False)
    for name, value in REQUIRED_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    load_settings.cache_clear()
    yield monkeypatch
    load_settings.cache_clear()


def query_returning(*documents: dict[str, Any]) -> Callable[..., list[dict[str, Any]]]:
    def query_items(**kwargs: Any) -> list[dict[str, Any]]:
        kwargs["response_hook"]({}, {"Documents": list(documents), "_count": len(documents)})
        return list(documents)

    return query_items
