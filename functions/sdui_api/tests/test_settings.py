import pytest

from settings import (
    DEFAULT_CACHE_MAX_AGE_SECONDS,
    DEFAULT_SCOPE,
    SettingsError,
    load_settings,
    parse_role_entitlements,
)


def test_role_entitlements_are_parsed_into_sets():
    parsed = parse_role_entitlements('{"BillingViewer": ["billing.read", "billing.read"]}')

    assert parsed == {"BillingViewer": frozenset({"billing.read"})}


def test_missing_configuration_yields_no_roles():
    assert parse_role_entitlements("{}") == {}


@pytest.mark.parametrize(
    "document",
    [
        pytest.param('["BillingViewer"]', id="not-object"),
        pytest.param('{"BillingViewer": "billing.read"}', id="string-instead-of-list"),
        pytest.param('{"BillingViewer": [7]}', id="non-string-entitlement"),
        pytest.param("{BillingViewer", id="invalid-json"),
    ],
)
def test_malformed_role_entitlements_are_rejected(document: str):
    with pytest.raises(ValueError):
        parse_role_entitlements(document)


def test_settings_default_optional_values(settings_environment: pytest.MonkeyPatch):
    settings = load_settings()

    assert settings.required_scope == DEFAULT_SCOPE
    assert settings.cache_max_age_seconds == DEFAULT_CACHE_MAX_AGE_SECONDS
    assert settings.role_entitlements == {}


def test_missing_variable_is_reported_by_name(settings_environment: pytest.MonkeyPatch):
    settings_environment.delenv("COSMOS_DATABASE")

    with pytest.raises(SettingsError) as error:
        load_settings()

    assert (error.value.variable, error.value.problem) == ("COSMOS_DATABASE", "missing")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        pytest.param("UI_CACHE_MAX_AGE_SECONDS", "sixty-seconds", id="integer"),
        pytest.param("ROLE_ENTITLEMENTS", '{"secret-looking-role": "entitlement"}', id="role-entitlements"),
    ],
)
def test_invalid_variable_is_reported_without_its_value(name: str, value: str, settings_environment: pytest.MonkeyPatch):
    settings_environment.setenv(name, value)

    with pytest.raises(SettingsError) as error:
        load_settings()

    assert (error.value.variable, error.value.problem) == (name, "invalid")
    assert error.value.__cause__ is None
    assert value not in str(error.value)
