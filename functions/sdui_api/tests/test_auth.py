import datetime as dt

import jwt
import pytest
from conftest import AUDIENCE, ISSUER, REQUIRED_SCOPE, SUBJECT
from jwt.exceptions import PyJWKClientConnectionError

from auth import AuthError, extract_bearer_token, mask_subject, verify_token


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


def test_verify_token_propagates_jwks_connection_failures(issue_token):
    def unreachable_resolver(token: str):
        raise PyJWKClientConnectionError("jwks unreachable")

    with pytest.raises(PyJWKClientConnectionError):
        _verify(issue_token(), unreachable_resolver)
