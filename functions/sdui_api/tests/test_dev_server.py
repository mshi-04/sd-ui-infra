from dev_server import parse_roles, resolve_payload

EXAMPLE_OID = "00000000-0000-0000-0000-000000000000"
UNKNOWN_OID = "99999999-9999-9999-9999-999999999999"


def test_unknown_surface_has_no_resolution():
    assert resolve_payload("missing", EXAMPLE_OID, frozenset()) is None


def test_seed_profile_receives_its_entitlements_and_preferences():
    payload, etag = resolve_payload("dashboard", EXAMPLE_OID, frozenset())
    component_ids = [component["id"] for component in payload["components"]]

    assert component_ids[0] == "billing-summary"
    assert payload["theme"] == "dark"
    assert etag.startswith('"')


def test_unknown_account_falls_back_to_the_base_definition():
    payload, _ = resolve_payload("dashboard", UNKNOWN_OID, frozenset())

    assert [component["id"] for component in payload["components"]] == ["usage-summary"]


def test_roles_header_changes_the_resolved_components():
    without_role, _ = resolve_payload("dashboard", UNKNOWN_OID, frozenset())
    with_role, _ = resolve_payload("dashboard", UNKNOWN_OID, frozenset({"SupportAgent"}))

    assert "impersonation-banner" not in [component["id"] for component in without_role["components"]]
    assert "impersonation-banner" in [component["id"] for component in with_role["components"]]


def test_roles_header_is_split_and_trimmed():
    assert parse_roles(" SupportAgent , UiAdmin ") == frozenset({"SupportAgent", "UiAdmin"})
    assert parse_roles(None) == frozenset()
    assert parse_roles("") == frozenset()
