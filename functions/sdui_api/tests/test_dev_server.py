import json
from pathlib import Path

import pytest

import dev_server
from dev_server import load_definitions, parse_roles, resolve_payload

EXAMPLE_OID = "00000000-0000-0000-0000-000000000000"
UNKNOWN_OID = "99999999-9999-9999-9999-999999999999"


@pytest.fixture
def definition_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    seed_root = tmp_path / "seed"
    definitions = seed_root / "ui_definitions"
    definitions.mkdir(parents=True)
    monkeypatch.setattr(dev_server, "SEED_ROOT", seed_root)
    return definitions


def _write_definition(root: Path, file: str, *, surface: str = "home", version: str, revision: str = "r1") -> None:
    document = {"id": f"{surface}:{version}", "surface": surface, "version": version, "revision": revision}
    (root / file).write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize("newest_file,oldest_file", [("a.json", "z.json"), ("z.json", "a.json")])
@pytest.mark.parametrize("older,newer", [("2026-06-01", "2026-07-01"), ("10", "9")])
def test_latest_definition_uses_string_version_independent_of_filename_and_revision(
    definition_root, newest_file, oldest_file, older, newer
):
    _write_definition(definition_root, newest_file, version=newer, revision="a")
    _write_definition(definition_root, oldest_file, version=older, revision="z")

    definition = load_definitions()["home"]

    assert definition.version == newer
    assert definition.revision == "a"


def test_latest_definition_is_selected_per_surface(definition_root):
    _write_definition(definition_root, "a-home-new.json", surface="home", version="9")
    _write_definition(definition_root, "b-settings-old.json", surface="settings", version="1")
    _write_definition(definition_root, "c-home-old.json", surface="home", version="10")
    _write_definition(definition_root, "d-settings-new.json", surface="settings", version="2")

    assert {surface: definition.version for surface, definition in load_definitions().items()} == {"home": "9", "settings": "2"}


@pytest.mark.parametrize("include_newer", [False, True])
def test_duplicate_surface_and_version_is_rejected_even_for_an_old_version(definition_root, include_newer):
    if include_newer:
        _write_definition(definition_root, "a-newest.json", version="9")
    _write_definition(definition_root, "b-first.json", version="1", revision="r1")
    _write_definition(definition_root, "z-duplicate.json", version="1", revision="r2")

    with pytest.raises(ValueError) as error:
        load_definitions()

    assert str(error.value) == (
        "seed/ui_definitions/z-duplicate.json: $.version: duplicates surface and version from seed/ui_definitions/b-first.json"
    )


def test_unknown_surface_has_no_resolution():
    assert resolve_payload("missing", EXAMPLE_OID, frozenset()) is None


def test_seed_profile_receives_its_entitlements_and_preferences():
    payload, etag = resolve_payload("dashboard", EXAMPLE_OID, frozenset())
    component_ids = [component["id"] for component in payload["components"]]

    assert component_ids[0] == "billing-summary"
    assert payload["theme"] == "dark"
    assert etag.startswith('"')


def test_single_definition_keeps_existing_payload_and_etag():
    payload, etag = resolve_payload("dashboard", UNKNOWN_OID, frozenset())

    assert payload == {
        "surface": "dashboard",
        "version": "2026-06-01",
        "revision": "a1b2c3",
        "theme": "light",
        "density": "comfortable",
        "components": [
            {
                "id": "usage-summary",
                "type": "Card",
                "props": {"title": "Usage", "span": 6},
                "children": [{"id": "usage-chart", "type": "Chart", "props": {"metric": "requests"}, "children": []}],
            }
        ],
    }
    assert etag == '"7d5691a9e0db87f3"'


def test_roles_header_changes_the_resolved_components():
    without_role, _ = resolve_payload("dashboard", UNKNOWN_OID, frozenset())
    with_role, _ = resolve_payload("dashboard", UNKNOWN_OID, frozenset({"SupportAgent"}))

    assert "impersonation-banner" not in [component["id"] for component in without_role["components"]]
    assert "impersonation-banner" in [component["id"] for component in with_role["components"]]


def test_roles_header_is_split_and_trimmed():
    assert parse_roles(" SupportAgent , UiAdmin ") == frozenset({"SupportAgent", "UiAdmin"})
    assert parse_roles(None) == frozenset()
    assert parse_roles("") == frozenset()


def test_app_role_opens_components_for_an_unknown_account():
    payload, _ = resolve_payload("dashboard", UNKNOWN_OID, frozenset({"BillingViewer"}))

    assert "billing-summary" in [component["id"] for component in payload["components"]]
