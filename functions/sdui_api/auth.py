import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from dependency_errors import DependencyUnavailableError

KeyResolver = Callable[[str], Any]

BEARER_PREFIX = "Bearer "
SIGNING_ALGORITHMS = ["RS256"]
REQUIRED_CLAIMS = ["exp", "nbf", "iss", "aud", "oid"]
JWKS_DEPENDENCY = "jwks"
SUBJECT_MASK_LENGTH = 12
JWKS_FETCH_TIMEOUT_SECONDS = 3


class AuthError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Principal:
    subject: str
    app_roles: frozenset[str]

    @property
    def masked_subject(self) -> str:
        return mask_subject(self.subject)


def mask_subject(subject: str) -> str:
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:SUBJECT_MASK_LENGTH]


def extract_bearer_token(authorization_header: str | None) -> str:
    if not authorization_header or not authorization_header.startswith(BEARER_PREFIX):
        raise AuthError("missing_bearer_token")
    token = authorization_header[len(BEARER_PREFIX) :].strip()
    if not token:
        raise AuthError("missing_bearer_token")
    return token


@lru_cache(maxsize=4)
def jwks_key_resolver(jwks_uri: str) -> KeyResolver:
    client = PyJWKClient(jwks_uri, cache_keys=True, timeout=JWKS_FETCH_TIMEOUT_SECONDS)

    def resolve(token: str) -> Any:
        return client.get_signing_key_from_jwt(token).key

    return resolve


def verify_token(
    token: str,
    *,
    key_resolver: KeyResolver,
    issuer: str,
    audience: str,
    required_scope: str,
) -> Principal:
    try:
        signing_key = key_resolver(token)
    except PyJWKClientConnectionError as error:
        raise DependencyUnavailableError(JWKS_DEPENDENCY, _failure_kind(error)) from error
    except jwt.PyJWTError as error:
        raise AuthError("unresolvable_signing_key") from error

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=SIGNING_ALGORITHMS,
            audience=audience,
            issuer=issuer,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as error:
        raise AuthError("expired_token") from error
    except jwt.InvalidAudienceError as error:
        raise AuthError("audience_mismatch") from error
    except jwt.InvalidIssuerError as error:
        raise AuthError("issuer_mismatch") from error
    except jwt.PyJWTError as error:
        raise AuthError("invalid_token") from error

    if required_scope not in str(claims.get("scp", "")).split():
        raise AuthError("insufficient_scope")

    return Principal(subject=claims["oid"], app_roles=frozenset(claims.get("roles", [])))


def _failure_kind(error: PyJWKClientConnectionError) -> str:
    return type(error.__cause__ or error).__name__
