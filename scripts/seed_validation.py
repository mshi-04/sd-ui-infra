import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

SEED_ROOT = Path(__file__).resolve().parents[1] / "seed"
SCHEMA_ROOT = SEED_ROOT / "schemas"

Rule = Callable[[Mapping[str, Any]], Iterator[tuple[str, str]]]


@dataclass(frozen=True)
class Finding:
    file: str
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.location}: {self.message}"


@dataclass(frozen=True)
class SeedDocument:
    directory: str
    file: str
    content: Mapping[str, Any]


@dataclass(frozen=True)
class SeedReport:
    documents: tuple[SeedDocument, ...]
    errors: tuple[Finding, ...]
    warnings: tuple[Finding, ...]


@dataclass(frozen=True)
class DocumentRules:
    errors: Rule
    warnings: Rule


def validate_seed(seed_root: Path = SEED_ROOT) -> SeedReport:
    documents: list[SeedDocument] = []
    errors: list[Finding] = []
    warnings: list[Finding] = []
    first_definition_file_by_version: dict[tuple[str, str], str] = {}

    for directory, rules in RULES_BY_DIRECTORY.items():
        validator = _schema_validator(directory)
        for path in sorted((seed_root / directory).glob("*.json")):
            file = path.relative_to(seed_root.parent).as_posix()
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
            except ValueError as error:
                errors.append(Finding(file, "$", f"is not valid UTF-8 JSON: {error}"))
                continue

            schema_errors = [Finding(file, error.json_path, _describe(error)) for error in validator.iter_errors(content)]
            errors.extend(schema_errors)
            if schema_errors:
                continue

            rule_errors = [Finding(file, location, message) for location, message in rules.errors(content)]
            if directory == "ui_definitions":
                key = (content["surface"], content["version"])
                first_file = first_definition_file_by_version.setdefault(key, file)
                if first_file != file:
                    rule_errors.append(Finding(file, "$.version", f"duplicates surface and version from {first_file}"))
            errors.extend(rule_errors)
            warnings.extend(Finding(file, location, message) for location, message in rules.warnings(content))
            if not rule_errors:
                documents.append(SeedDocument(directory, file, content))

    return SeedReport(tuple(documents), tuple(errors), tuple(warnings))


def _schema_validator(directory: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_ROOT / f"{directory}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _describe(error: ValidationError) -> str:
    # error.message embeds the offending value, which for profiles can be the whole document.
    if error.validator == "required":
        return error.message
    if error.validator == "type":
        return f"must be of type {error.validator_value}"
    return f"violates {error.validator} {error.validator_value!r}"


def _definition_errors(definition: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    expected_id = f"{definition['surface']}:{definition['version']}"
    if definition["id"] != expected_id:
        yield "$.id", f"must equal surface:version ({expected_id!r})"

    for location, components in _sibling_arrays(definition):
        yield from _duplicate_ids(location, components)


def _definition_warnings(definition: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    for location, components in _sibling_arrays(definition):
        for index, component in enumerate(components):
            for key, value in component.get("props", {}).items():
                if isinstance(value, dict | list):
                    yield (
                        f"{location}[{index}].props.{key}",
                        "is not a scalar; the Android client discards object and array props",
                    )


def _sibling_arrays(definition: Mapping[str, Any]) -> Iterator[tuple[str, Sequence[Mapping[str, Any]]]]:
    yield from _nested_sibling_arrays("$.components", definition.get("components", []))
    for index, variant in enumerate(definition.get("variants", [])):
        yield from _nested_sibling_arrays(f"$.variants[{index}].components", variant.get("components", []))


def _nested_sibling_arrays(
    location: str, components: Sequence[Mapping[str, Any]]
) -> Iterator[tuple[str, Sequence[Mapping[str, Any]]]]:
    yield location, components
    for index, component in enumerate(components):
        yield from _nested_sibling_arrays(f"{location}[{index}].children", component.get("children", []))


def _duplicate_ids(location: str, components: Sequence[Mapping[str, Any]]) -> Iterator[tuple[str, str]]:
    first_index_by_id: dict[str, int] = {}
    for index, component in enumerate(components):
        first_index = first_index_by_id.setdefault(component["id"], index)
        if first_index != index:
            yield f"{location}[{index}].id", f"duplicates the id of sibling {location}[{first_index}]"


def _profile_errors(profile: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    if profile["id"] != profile["userId"]:
        yield "$.id", "must equal userId"


def _no_findings(document: Mapping[str, Any]) -> Iterator[tuple[str, str]]:
    yield from ()


RULES_BY_DIRECTORY = {
    "ui_definitions": DocumentRules(errors=_definition_errors, warnings=_definition_warnings),
    "account_profiles": DocumentRules(errors=_profile_errors, warnings=_no_findings),
}
