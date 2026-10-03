import json
from pathlib import Path

import pytest

from auth import Principal
from models import AccountProfile, UiDefinition
from seed_validation import RULES_BY_DIRECTORY, SCHEMA_ROOT, validate_seed
from ui_resolver import resolve

SEED_ROOT = Path(__file__).resolve().parents[3] / "seed"
APP_ROLES_PATH = Path(__file__).resolve().parents[3] / "config" / "app_roles.json"


def _load(relative_path: str) -> dict:
    return json.loads((SEED_ROOT / relative_path).read_text(encoding="utf-8"))


def _role_entitlements() -> dict[str, frozenset[str]]:
    roles = json.loads(APP_ROLES_PATH.read_text(encoding="utf-8"))
    return {name: frozenset(role["entitlements"]) for name, role in roles.items()}


@pytest.fixture
def dashboard() -> UiDefinition:
    return UiDefinition.from_document(_load("ui_definitions/dashboard.json"))


@pytest.fixture
def example_profile() -> AccountProfile:
    return AccountProfile.from_document(_load("account_profiles/example.json"))


def test_every_seed_document_passes_validation():
    report = validate_seed(SEED_ROOT)

    assert [str(error) for error in report.errors] == []
    assert report.documents


def test_every_seed_directory_is_covered_by_validation():
    directories = {path.name for path in SEED_ROOT.iterdir() if path.is_dir()}

    assert directories == {*RULES_BY_DIRECTORY, SCHEMA_ROOT.name}


def test_seed_documents_resolve_for_the_example_profile(dashboard, example_profile):
    resolved = resolve(
        dashboard, example_profile, Principal(subject=example_profile.user_id, app_roles=frozenset()), _role_entitlements()
    )
    component_ids = [component.id for component in resolved.components]

    assert component_ids[0] == "billing-summary"
    assert "impersonation-banner" in component_ids
    assert resolved.theme == "dark"


def test_seed_definition_hides_components_without_entitlements(dashboard):
    anonymous = AccountProfile.empty("unknown-oid")

    resolved = resolve(dashboard, anonymous, Principal(subject="unknown-oid", app_roles=frozenset()), _role_entitlements())

    assert [component.id for component in resolved.components] == ["usage-summary"]


def test_configured_roles_open_the_seeded_components(dashboard):
    anonymous = AccountProfile.empty("unknown-oid")

    resolved = resolve(
        dashboard,
        anonymous,
        Principal(subject="unknown-oid", app_roles=frozenset({"BillingViewer"})),
        _role_entitlements(),
    )

    assert "billing-summary" in [component.id for component in resolved.components]


def _seed_ui_definitions() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((SEED_ROOT / "ui_definitions").glob("*.json"))]


def _seed_account_profiles() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((SEED_ROOT / "account_profiles").glob("*.json"))]


def _walk_components(components: list[dict]):
    for component in components:
        yield component
        yield from _walk_components(component.get("children", []))


def _all_seed_components(definition: dict):
    yield from _walk_components(definition["components"])
    for variant in definition.get("variants", []):
        yield from _walk_components(variant["components"])


def test_seed_variant_audiences_are_defined_roles_or_profile_audiences():
    known = set(_role_entitlements())
    for profile in _seed_account_profiles():
        known.update(profile.get("audiences", []))

    audiences = {variant["audience"] for definition in _seed_ui_definitions() for variant in definition.get("variants", [])}

    assert sorted(audiences - known) == []


def test_seed_required_entitlements_are_granted_by_a_role_or_a_profile():
    granted = {entitlement for entitlements in _role_entitlements().values() for entitlement in entitlements}
    for profile in _seed_account_profiles():
        granted.update(profile.get("entitlements", []))

    required = {
        entitlement
        for definition in _seed_ui_definitions()
        for component in _all_seed_components(definition)
        for entitlement in component.get("requiredEntitlements", [])
    }

    assert sorted(required - granted) == []
