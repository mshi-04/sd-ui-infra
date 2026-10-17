import datetime as dt
import io
import json
import logging
import time
from types import SimpleNamespace
from urllib.error import URLError

import jwt
import pytest
from conftest import AUDIENCE, ISSUER, REQUIRED_SCOPE, SUBJECT, jwk_for
from jwt import api_jwk, jwk_set_cache, jwks_client
from jwt.exceptions import PyJWKClientConnectionError

import auth
from auth import AuthError, extract_bearer_token, mask_subject, verify_token
from dependency_errors import DependencyUnavailableError


def _verify(token: str, key_resolver, **overrides):
    arguments = {
        "key_resolver": key_resolver,
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "required_scope": REQUIRED_SCOPE,
    }
    arguments.update(overrides)
    return verify_token(token, **arguments)


def test_verify_token_returns_principal(issue_token, key_resolver):
    principal = _verify(issue_token(), key_resolver)

    assert principal.subject == SUBJECT
    assert principal.app_roles == frozenset({"BillingViewer"})


def test_verify_token_accepts_multiple_scopes(issue_token, key_resolver):
    principal = _verify(issue_token(scp=f"openid {REQUIRED_SCOPE}"), key_resolver)

    assert principal.subject == SUBJECT


def test_verify_token_rejects_expired_token(issue_token, key_resolver):
    expired = dt.datetime.now(tz=dt.UTC) - dt.timedelta(minutes=5)

    with pytest.raises(AuthError) as error:
        _verify(issue_token(exp=expired, nbf=expired - dt.timedelta(minutes=10)), key_resolver)

    assert error.value.reason == "expired_token"


def test_verify_token_rejects_audience_mismatch(issue_token, key_resolver):
    with pytest.raises(AuthError) as error:
        _verify(issue_token(aud="00000000-0000-0000-0000-000000000000"), key_resolver)

    assert error.value.reason == "audience_mismatch"


def test_verify_token_rejects_issuer_mismatch(issue_token, key_resolver):
    with pytest.raises(AuthError) as error:
        _verify(issue_token(iss="https://login.microsoftonline.com/other/v2.0"), key_resolver)

    assert error.value.reason == "issuer_mismatch"


def test_verify_token_rejects_insufficient_scope(issue_token, key_resolver):
    with pytest.raises(AuthError) as error:
        _verify(issue_token(scp="openid"), key_resolver)

    assert error.value.reason == "insufficient_scope"


def test_verify_token_rejects_missing_oid(issue_token, key_resolver):
    with pytest.raises(AuthError) as error:
        _verify(issue_token(oid=None), key_resolver)

    assert error.value.reason == "invalid_token"


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer "])
def test_extract_bearer_token_rejects_invalid_header(header):
    with pytest.raises(AuthError) as error:
        extract_bearer_token(header)

    assert error.value.reason == "missing_bearer_token"


def test_extract_bearer_token_returns_token():
    assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"


def test_mask_subject_hides_raw_value():
    masked = mask_subject(SUBJECT)

    assert SUBJECT not in masked
    assert masked == mask_subject(SUBJECT)


def test_verify_token_rejects_a_token_whose_key_cannot_be_resolved():
    def failing_resolver(token: str):
        raise jwt.DecodeError("not a jwt")

    with pytest.raises(AuthError) as error:
        _verify("not-a-jwt", failing_resolver)

    assert error.value.reason == "unresolvable_signing_key"


def test_verify_token_reports_jwks_connection_failures_as_unavailable_dependency(issue_token):
    token = issue_token()

    def unreachable_resolver(token: str):
        raise PyJWKClientConnectionError(f"jwks unreachable for {token}") from URLError(TimeoutError("timed out"))

    with pytest.raises(DependencyUnavailableError) as error:
        _verify(token, unreachable_resolver)

    assert (error.value.dependency, error.value.detail) == ("jwks", "URLError")
    assert token not in str(error.value)


def test_jwks_client_is_bounded_and_refreshes_the_whole_key_set(monkeypatch):
    clients = []
    real_client = auth.StaleIfErrorJWKClient

    def capture(*args, **kwargs):
        clients.append(real_client(*args, **kwargs))
        return clients[-1]

    monkeypatch.setattr(auth, "StaleIfErrorJWKClient", capture)
    auth.jwks_key_resolver.cache_clear()

    try:
        auth.jwks_key_resolver("https://example.invalid/keys")
    finally:
        auth.jwks_key_resolver.cache_clear()

    (client,) = clients
    assert client.uri == "https://example.invalid/keys"
    assert client.timeout == 3
    assert client.jwk_set_cache.lifespan == 300
    assert client.cooldown_duration == 30
    assert "get_signing_key" not in vars(client)


JWKS_URI = "https://example.invalid/keys"
KID = "key-1"
NEW_KID = "key-2"
LIFESPAN = auth.JWKS_LIFESPAN_SECONDS
COOLDOWN = auth.JWKS_REFRESH_COOLDOWN_SECONDS
STALE_LIMIT = auth.JWKS_STALE_LIMIT_SECONDS


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


class FakeJwksEndpoint:
    def __init__(self) -> None:
        self.keys: list[dict] = []
        self.failing = False
        self.calls = 0

    def build_opener(self, *handlers):
        return self

    def open(self, request, timeout):
        self.calls += 1
        if self.failing:
            raise URLError(TimeoutError("timed out"))
        return io.BytesIO(json.dumps({"keys": self.keys}).encode("utf-8"))


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    clock = FakeClock()
    fake_time = SimpleNamespace(**{name: getattr(time, name) for name in dir(time) if not name.startswith("__")})
    fake_time.monotonic = clock.monotonic
    for module in (auth, jwks_client, jwk_set_cache, api_jwk):
        monkeypatch.setattr(module, "time", fake_time)
    return clock


@pytest.fixture
def endpoint(monkeypatch, clock, private_key) -> FakeJwksEndpoint:
    endpoint = FakeJwksEndpoint()
    endpoint.keys = [jwk_for(private_key.public_key(), KID)]
    monkeypatch.setattr(jwks_client.urllib.request, "build_opener", endpoint.build_opener)
    return endpoint


@pytest.fixture
def resolver(endpoint):
    auth.jwks_key_resolver.cache_clear()
    yield auth.jwks_key_resolver(JWKS_URI)
    auth.jwks_key_resolver.cache_clear()


def test_resolver_verifies_a_token_through_the_jwks_endpoint(issue_token, resolver, endpoint):
    principal = _verify(issue_token(kid=KID), resolver)

    assert principal.subject == SUBJECT
    assert endpoint.calls == 1


def test_resolver_serves_repeated_tokens_from_the_cached_key_set(issue_token, resolver, endpoint, clock):
    _verify(issue_token(kid=KID), resolver)
    clock.advance(LIFESPAN - 1)
    _verify(issue_token(kid=KID), resolver)

    assert endpoint.calls == 1


def test_resolver_rejects_a_removed_key_once_the_key_set_expires(issue_token, resolver, endpoint, clock, other_private_key):
    token = issue_token(kid=KID)
    _verify(token, resolver)
    endpoint.keys = [jwk_for(other_private_key.public_key(), NEW_KID)]
    clock.advance(LIFESPAN + 1)

    with pytest.raises(AuthError) as error:
        _verify(token, resolver)

    assert error.value.reason == "unresolvable_signing_key"


def test_resolver_keeps_verifying_with_the_last_key_set_when_the_fetch_fails(issue_token, resolver, endpoint, clock, caplog):
    token = issue_token(kid=KID)
    _verify(token, resolver)
    endpoint.failing = True
    clock.advance(LIFESPAN + 1)

    with caplog.at_level(logging.WARNING, logger="auth"):
        principal = _verify(token, resolver)

    assert principal.subject == SUBJECT
    assert [record.getMessage() for record in caplog.records] == [
        f"Serving stale JWKS after fetch failure: age_seconds={LIFESPAN + 1}"
    ]
    assert token not in caplog.text
    assert JWKS_URI not in caplog.text


def test_resolver_does_not_extend_the_stale_window_while_serving_stale_keys(issue_token, resolver, endpoint, clock):
    token = issue_token(kid=KID)
    _verify(token, resolver)
    endpoint.failing = True
    clock.advance(STALE_LIMIT - 1)
    _verify(token, resolver)
    clock.advance(LIFESPAN + 1)

    with pytest.raises(DependencyUnavailableError) as error:
        _verify(token, resolver)

    assert error.value.dependency == "jwks"


def test_resolver_reports_unavailable_when_the_failure_outlasts_the_stale_limit(issue_token, resolver, endpoint, clock):
    token = issue_token(kid=KID)
    _verify(token, resolver)
    endpoint.failing = True
    clock.advance(STALE_LIMIT + 1)

    with pytest.raises(DependencyUnavailableError) as error:
        _verify(token, resolver)

    assert error.value.dependency == "jwks"


def test_resolver_reports_unavailable_when_no_fetch_ever_succeeded(issue_token, resolver, endpoint):
    endpoint.failing = True

    with pytest.raises(DependencyUnavailableError) as error:
        _verify(issue_token(kid=KID), resolver)

    assert error.value.dependency == "jwks"


def test_resolver_rejects_a_new_kid_during_an_outage(issue_token, resolver, endpoint, clock, other_private_key):
    _verify(issue_token(kid=KID), resolver)
    endpoint.failing = True
    clock.advance(LIFESPAN + 1)

    with pytest.raises(AuthError) as error:
        _verify(issue_token(kid=NEW_KID, signing_key=other_private_key), resolver)

    assert error.value.reason == "unresolvable_signing_key"


def test_resolver_forces_at_most_one_refresh_per_cooldown_for_unknown_kids(
    issue_token, resolver, endpoint, clock, other_private_key
):
    _verify(issue_token(kid=KID), resolver)
    unknown = issue_token(kid="unknown", signing_key=other_private_key)
    clock.advance(COOLDOWN + 1)

    for _ in range(3):
        with pytest.raises(AuthError):
            _verify(unknown, resolver)
    assert endpoint.calls == 2

    clock.advance(COOLDOWN + 1)
    with pytest.raises(AuthError):
        _verify(unknown, resolver)

    assert endpoint.calls == 3
