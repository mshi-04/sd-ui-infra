from constants import parse_role_entitlements


def test_role_entitlements_are_parsed_into_sets():
    parsed = parse_role_entitlements('{"BillingViewer": ["billing.read", "billing.read"]}')

    assert parsed == {"BillingViewer": frozenset({"billing.read"})}


def test_missing_configuration_yields_no_roles():
    assert parse_role_entitlements("{}") == {}
