import json
from pathlib import Path

import pytest

from auth import Principal
from models import AccountProfile, UiDefinition
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


def test_seed_definition_id_matches_surface_and_version():
    document = _load("ui_definitions/dashboard.json")

    assert document["id"] == f"{document['surface']}:{document['version']}"


def test_seed_profile_id_matches_user_id():
    document = _load("account_profiles/example.json")

    assert document["id"] == document["userId"]


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
