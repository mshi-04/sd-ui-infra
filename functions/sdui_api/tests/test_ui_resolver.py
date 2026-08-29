import pytest

from auth import Principal
from models import AccountProfile, Preferences, UiDefinition
from ui_resolver import etag_of, resolve

BASE_DOCUMENT = {
    "surface": "dashboard",
    "version": "2026-06-01",
    "revision": "a1b2c3",
    "components": [
        {"id": "usage-summary", "type": "Card", "props": {"title": "Usage"}},
        {
            "id": "billing-summary",
            "type": "Card",
            "props": {"title": "Billing"},
            "requiredEntitlements": ["billing.read"],
            "children": [
                {"id": "invoice-list", "type": "List", "props": {}},
                {"id": "refund-action", "type": "Button", "props": {}, "requiredEntitlements": ["billing.write"]},
            ],
        },
    ],
    "variants": [
        {
            "audience": "SupportAgent",
            "components": [
                {"id": "usage-summary", "type": "Card", "props": {"title": "Customer usage"}},
                {"id": "impersonation-banner", "type": "Banner", "props": {}},
            ],
        }
    ],
}


@pytest.fixture
def definition() -> UiDefinition:
    return UiDefinition.from_document(BASE_DOCUMENT)


ROLE_ENTITLEMENTS = {
    "UiAdmin": frozenset({"billing.read", "billing.write", "support.read"}),
    "BillingViewer": frozenset({"billing.read"}),
    "SupportAgent": frozenset({"support.read"}),
}


def _principal(*roles: str) -> Principal:
    return Principal(subject="user-oid", app_roles=frozenset(roles))


def _resolve(definition: UiDefinition, profile: AccountProfile, principal: Principal):
    return resolve(definition, profile, principal, ROLE_ENTITLEMENTS)


def _component_ids(resolved) -> list[str]:
    return [component.id for component in resolved.components]


def test_components_requiring_missing_entitlements_are_removed(definition):
    resolved = _resolve(definition, AccountProfile.empty("user-oid"), _principal())

    assert _component_ids(resolved) == ["usage-summary"]


def test_granted_entitlement_keeps_component_and_filters_children(definition):
    profile = AccountProfile(user_id="user-oid", entitlements=frozenset({"billing.read"}))

    resolved = _resolve(definition, profile, _principal())
    billing = next(component for component in resolved.components if component.id == "billing-summary")

    assert [child.id for child in billing.children] == ["invoice-list"]


def test_variant_applies_only_to_matching_audience(definition):
    profile = AccountProfile.empty("user-oid")

    without_role = _resolve(definition, profile, _principal())
    with_role = _resolve(definition, profile, _principal("SupportAgent"))

    assert without_role.components[0].props["title"] == "Usage"
    assert with_role.components[0].props["title"] == "Customer usage"
    assert "impersonation-banner" in _component_ids(with_role)


def test_variant_audience_can_come_from_profile(definition):
    profile = AccountProfile(user_id="user-oid", audiences=frozenset({"SupportAgent"}))

    resolved = _resolve(definition, profile, _principal())

    assert "impersonation-banner" in _component_ids(resolved)


def test_entitlements_are_applied_after_variants(definition):
    profile = AccountProfile(user_id="user-oid", audiences=frozenset({"SupportAgent"}))

    resolved = _resolve(definition, profile, _principal())

    assert "billing-summary" not in _component_ids(resolved)


def test_pinned_components_are_moved_to_the_front(definition):
    profile = AccountProfile(
        user_id="user-oid",
        entitlements=frozenset({"billing.read"}),
        preferences=Preferences(pinned_component_ids=("billing-summary",)),
    )

    resolved = _resolve(definition, profile, _principal())

    assert _component_ids(resolved) == ["billing-summary", "usage-summary"]


def test_preferences_are_returned_in_payload(definition):
    profile = AccountProfile(user_id="user-oid", preferences=Preferences(theme="dark", density="compact"))

    payload = _resolve(definition, profile, _principal()).to_payload()

    assert payload["theme"] == "dark"
    assert payload["density"] == "compact"
    assert payload["revision"] == "a1b2c3"


def test_payload_hides_entitlement_requirements(definition):
    profile = AccountProfile(user_id="user-oid", entitlements=frozenset({"billing.read"}))

    payload = _resolve(definition, profile, _principal()).to_payload()

    assert "requiredEntitlements" not in payload["components"][1]


def test_etag_differs_per_resolution(definition):
    entitled = AccountProfile(user_id="user-oid", entitlements=frozenset({"billing.read"}))
    plain = AccountProfile.empty("user-oid")

    assert etag_of(_resolve(definition, entitled, _principal())) != etag_of(_resolve(definition, plain, _principal()))
    assert etag_of(_resolve(definition, plain, _principal())) == etag_of(_resolve(definition, plain, _principal()))


def test_app_role_grants_entitlement_without_a_profile(definition):
    resolved = _resolve(definition, AccountProfile.empty("user-oid"), _principal("BillingViewer"))

    assert "billing-summary" in _component_ids(resolved)


def test_ui_admin_role_reaches_nested_components(definition):
    resolved = _resolve(definition, AccountProfile.empty("user-oid"), _principal("UiAdmin"))
    billing = next(component for component in resolved.components if component.id == "billing-summary")

    assert [child.id for child in billing.children] == ["invoice-list", "refund-action"]


def test_profile_entitlements_extend_role_entitlements(definition):
    profile = AccountProfile(user_id="user-oid", entitlements=frozenset({"billing.write"}))

    resolved = _resolve(definition, profile, _principal("BillingViewer"))
    billing = next(component for component in resolved.components if component.id == "billing-summary")

    assert [child.id for child in billing.children] == ["invoice-list", "refund-action"]


def test_unknown_role_grants_nothing(definition):
    resolved = _resolve(definition, AccountProfile.empty("user-oid"), _principal("Unmapped"))

    assert _component_ids(resolved) == ["usage-summary"]
