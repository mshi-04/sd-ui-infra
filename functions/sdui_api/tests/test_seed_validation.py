import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from models import AccountProfile, Preferences, UiDefinition
from seed_validation import RULES_BY_DIRECTORY, SCHEMA_ROOT, validate_seed

USER_ID = "44444444-4444-4444-4444-444444444444"


def _definition(**overrides: Any) -> dict[str, Any]:
    document = {
        "id": "home:2026-07-01",
        "surface": "home",
        "version": "2026-07-01",
        "revision": "r1",
        "components": [
            {
                "id": "summary",
                "type": "Card",
                "props": {"title": "Summary"},
                "children": [{"id": "chart", "type": "Chart"}],
            },
            {"id": "actions", "type": "List"},
        ],
        "variants": [{"audience": "SupportAgent", "components": [{"id": "summary", "type": "Card", "props": {"title": "Ops"}}]}],
    }
    document.update(overrides)
    return document


def _profile(**overrides: Any) -> dict[str, Any]:
    document = {
        "id": USER_ID,
        "userId": USER_ID,
        "entitlements": ["billing.read"],
        "audiences": ["SupportAgent"],
        "preferences": {"theme": "dark", "density": "compact", "pinnedComponentIds": ["summary"]},
    }
    document.update(overrides)
    return document


def _seed_root(tmp_path: Path, *, definitions: dict[str, Any] | None = None, profiles: dict[str, Any] | None = None) -> Path:
    seed_root = tmp_path / "seed"
    for directory, documents in (("ui_definitions", definitions or {}), ("account_profiles", profiles or {})):
        (seed_root / directory).mkdir(parents=True)
        for name, document in documents.items():
            text = document if isinstance(document, str) else json.dumps(document)
            (seed_root / directory / name).write_text(text, encoding="utf-8")
    return seed_root


def _messages(tmp_path: Path, **documents: dict[str, Any]) -> list[str]:
    return [str(error) for error in validate_seed(_seed_root(tmp_path, **documents)).errors]


@pytest.mark.parametrize("directory", list(RULES_BY_DIRECTORY))
def test_schemas_are_valid_draft_2020_12(directory):
    Draft202012Validator.check_schema(json.loads((SCHEMA_ROOT / f"{directory}.schema.json").read_text(encoding="utf-8")))


def test_valid_documents_produce_no_findings(tmp_path):
    report = validate_seed(_seed_root(tmp_path, definitions={"home.json": _definition()}, profiles={"user.json": _profile()}))

    assert report.errors == ()
    assert report.warnings == ()
    assert [document.file for document in report.documents] == [
        "seed/ui_definitions/home.json",
        "seed/account_profiles/user.json",
    ]


def test_optional_fields_may_be_omitted_and_keep_their_defaults(tmp_path):
    definition = {
        "id": "home:1",
        "surface": "home",
        "version": "1",
        "revision": "r1",
        "components": [{"id": "a", "type": "Card"}],
    }
    profile = {"id": USER_ID, "userId": USER_ID}

    report = validate_seed(_seed_root(tmp_path, definitions={"home.json": definition}, profiles={"user.json": profile}))

    assert report.errors == ()
    assert UiDefinition.from_document(definition).variants == ()
    assert UiDefinition.from_document(definition).components[0].children == ()
    assert AccountProfile.from_document(profile).preferences == Preferences()


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (_definition(revision=None), "$.revision: must be of type string"),
        (_definition(components={}), "$.components: must be of type array"),
        (_definition(variants=None), "$.variants: must be of type array"),
        (_definition(surface=""), "$.surface: violates minLength 1"),
        (_definition(components=[{"id": "a", "type": "Card", "props": ["x"]}]), "$.components[0].props: must be of type object"),
        (
            _definition(components=[{"id": "a", "type": "Card", "requiredEntitlements": "billing.read"}]),
            "$.components[0].requiredEntitlements: must be of type array",
        ),
        (
            _definition(components=[{"id": "a", "type": "Card", "children": [{"id": "b"}]}]),
            "$.components[0].children[0]: 'type' is a required property",
        ),
        (_definition(variants=[{"components": []}]), "$.variants[0]: 'audience' is a required property"),
        (["not", "an", "object"], "$: must be of type object"),
    ],
)
def test_invalid_definition_is_reported_with_its_location(tmp_path, document, expected):
    assert _messages(tmp_path, definitions={"home.json": document}) == [f"seed/ui_definitions/home.json: {expected}"]


def test_missing_field_is_distinguished_from_wrong_type(tmp_path):
    missing = {key: value for key, value in _definition().items() if key != "revision"}

    assert _messages(tmp_path, definitions={"missing.json": missing, "wrong.json": _definition(revision=1)}) == [
        "seed/ui_definitions/missing.json: $: 'revision' is a required property",
        "seed/ui_definitions/wrong.json: $.revision: must be of type string",
    ]


def test_definition_id_must_match_surface_and_version(tmp_path):
    assert _messages(tmp_path, definitions={"home.json": _definition(id="home:latest")}) == [
        "seed/ui_definitions/home.json: $.id: must equal surface:version ('home:2026-07-01')"
    ]


def test_profile_id_must_match_user_id_without_echoing_identifiers(tmp_path):
    messages = _messages(tmp_path, profiles={"user.json": _profile(id="55555555-5555-5555-5555-555555555555")})

    assert messages == ["seed/account_profiles/user.json: $.id: must equal userId"]
    assert USER_ID not in messages[0]


def test_profile_errors_do_not_echo_the_offending_values(tmp_path):
    messages = _messages(
        tmp_path, profiles={"user.json": _profile(preferences=["private-value"], entitlements={"private": "value"})}
    )

    assert messages == [
        "seed/account_profiles/user.json: $.entitlements: must be of type array",
        "seed/account_profiles/user.json: $.preferences: must be of type object",
    ]


def test_unknown_component_type_and_props_keys_are_accepted(tmp_path):
    component = {"id": "future", "type": "HologramPanel", "props": {"brandNewKey": "x", "span": 4, "visible": True}}

    assert _messages(tmp_path, definitions={"home.json": _definition(components=[component])}) == []


def test_unknown_document_fields_are_accepted(tmp_path):
    assert _messages(tmp_path, definitions={"home.json": _definition(_etag="stored-by-cosmos", layout="grid")}) == []


def test_variant_may_override_a_base_component_id(tmp_path):
    override = {"id": "summary", "type": "Card", "children": [{"id": "chart", "type": "Chart", "props": {"metric": "errors"}}]}

    assert (
        _messages(tmp_path, definitions={"home.json": _definition(variants=[{"audience": "UiAdmin", "components": [override]}])})
        == []
    )


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"components": [{"id": "a", "type": "Card"}, {"id": "b", "type": "Card"}, {"id": "a", "type": "List"}]},
            "$.components[2].id: duplicates the id of sibling $.components[0]",
        ),
        (
            {
                "components": [
                    {"id": "a", "type": "Card", "children": [{"id": "c", "type": "Chart"}, {"id": "c", "type": "List"}]}
                ]
            },
            "$.components[0].children[1].id: duplicates the id of sibling $.components[0].children[0]",
        ),
        (
            {"variants": [{"audience": "UiAdmin", "components": [{"id": "x", "type": "Panel"}, {"id": "x", "type": "Panel"}]}]},
            "$.variants[0].components[1].id: duplicates the id of sibling $.variants[0].components[0]",
        ),
    ],
)
def test_duplicate_ids_among_siblings_are_rejected(tmp_path, overrides, expected):
    assert _messages(tmp_path, definitions={"home.json": _definition(**overrides)}) == [
        f"seed/ui_definitions/home.json: {expected}"
    ]


def test_the_same_id_in_different_sibling_arrays_is_accepted(tmp_path):
    components = [{"id": "a", "type": "Card", "children": [{"id": "a", "type": "Chart"}]}, {"id": "b", "type": "Card"}]

    assert _messages(tmp_path, definitions={"home.json": _definition(components=components)}) == []


def test_non_scalar_props_are_warnings_not_errors(tmp_path):
    components = [{"id": "a", "type": "Card", "children": [{"id": "b", "type": "List", "props": {"items": [1], "style": {}}}]}]

    report = validate_seed(_seed_root(tmp_path, definitions={"home.json": _definition(components=components)}))

    assert report.errors == ()
    assert [f"{warning.location}: {warning.message}" for warning in report.warnings] == [
        "$.components[0].children[0].props.items: is not a scalar; the Android client discards object and array props",
        "$.components[0].children[0].props.style: is not a scalar; the Android client discards object and array props",
    ]
    assert len(report.documents) == 1


def test_malformed_json_is_reported(tmp_path):
    messages = _messages(tmp_path, definitions={"broken.json": '{"id": '})

    assert len(messages) == 1
    assert messages[0].startswith("seed/ui_definitions/broken.json: $: is not valid UTF-8 JSON:")


def test_every_file_is_validated_and_invalid_documents_are_not_returned(tmp_path):
    report = validate_seed(
        _seed_root(
            tmp_path,
            definitions={"a.json": _definition(revision=1), "b.json": _definition()},
            profiles={"c.json": _profile(userId="other"), "d.json": _profile()},
        )
    )

    assert [error.file for error in report.errors] == [
        "seed/ui_definitions/a.json",
        "seed/account_profiles/c.json",
    ]
    assert [document.file for document in report.documents] == [
        "seed/ui_definitions/b.json",
        "seed/account_profiles/d.json",
    ]
