import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import seed_cosmos
from seed_validation import RULES_BY_DIRECTORY, SEED_ROOT

ENDPOINT = "https://cosmos.example.invalid:443/"


class RecordingCosmosClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.database_name: str | None = None
        self.upserts: list[tuple[str, dict]] = []

    def get_database_client(self, database_name: str) -> "RecordingCosmosClient":
        self.database_name = database_name
        return self

    def get_container_client(self, container_name: str) -> "RecordingContainer":
        return RecordingContainer(self, container_name)


class RecordingContainer:
    def __init__(self, client: RecordingCosmosClient, name: str) -> None:
        self._client = client
        self._name = name

    def upsert_item(self, document: dict) -> None:
        self._client.upserts.append((self._name, document))


def _refuse_construction(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("dry run must not construct Azure clients or credentials")


@pytest.fixture
def seed_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "seed"
    for directory in RULES_BY_DIRECTORY:
        shutil.copytree(SEED_ROOT / directory, root / directory)
    monkeypatch.setattr(seed_cosmos, "SEED_ROOT", root)
    for variable in ("COSMOS_ENDPOINT", "COSMOS_DATABASE", *seed_cosmos.CONTAINER_BY_DIRECTORY.values()):
        monkeypatch.delenv(variable, raising=False)
    return root


@pytest.fixture
def cosmos(monkeypatch: pytest.MonkeyPatch) -> list[RecordingCosmosClient]:
    clients: list[RecordingCosmosClient] = []

    def create(endpoint: str, credential: Any) -> RecordingCosmosClient:
        clients.append(RecordingCosmosClient(endpoint))
        return clients[-1]

    monkeypatch.setattr(seed_cosmos, "CosmosClient", create)
    monkeypatch.setattr(seed_cosmos, "DefaultAzureCredential", lambda: object())
    return clients


def test_container_mapping_covers_every_validated_directory():
    assert set(seed_cosmos.CONTAINER_BY_DIRECTORY) == set(RULES_BY_DIRECTORY)


def test_dry_run_needs_no_endpoint_and_constructs_no_azure_client(seed_root, monkeypatch, capsys):
    monkeypatch.setattr(seed_cosmos, "CosmosClient", _refuse_construction)
    monkeypatch.setattr(seed_cosmos, "DefaultAzureCredential", _refuse_construction)

    assert seed_cosmos.main(["--dry-run"]) == 0

    output = capsys.readouterr().out
    assert "would upsert seed/ui_definitions/dashboard.json into ui_definitions" in output
    assert "would upsert seed/account_profiles/example.json into account_profiles" in output
    assert "validated 2 documents; dry run wrote nothing" in output


def test_dry_run_fails_on_invalid_seed(seed_root, monkeypatch, capsys):
    monkeypatch.setattr(seed_cosmos, "CosmosClient", _refuse_construction)
    monkeypatch.setattr(seed_cosmos, "DefaultAzureCredential", _refuse_construction)
    (seed_root / "ui_definitions" / "broken.json").write_text('{"id": "broken"}', encoding="utf-8")

    assert seed_cosmos.main(["--dry-run"]) == 1

    captured = capsys.readouterr()
    assert "would upsert" not in captured.out
    assert "error: seed/ui_definitions/broken.json: $: 'surface' is a required property" in captured.err


def test_upsert_requires_an_endpoint(seed_root, cosmos, capsys):
    with pytest.raises(SystemExit) as exit_info:
        seed_cosmos.main([])

    assert exit_info.value.code == 2
    assert "--endpoint or COSMOS_ENDPOINT is required" in capsys.readouterr().err
    assert cosmos == []


def test_upsert_writes_every_document_after_validation(seed_root, cosmos, monkeypatch):
    monkeypatch.setenv("UI_DEFINITIONS_CONTAINER", "definitions")

    assert seed_cosmos.main(["--endpoint", ENDPOINT, "--database", "sdui-test"]) == 0

    [client] = cosmos
    assert client.endpoint == ENDPOINT
    assert client.database_name == "sdui-test"
    assert [(container, document["id"]) for container, document in client.upserts] == [
        ("definitions", "dashboard:2026-06-01"),
        ("account_profiles", "00000000-0000-0000-0000-000000000000"),
    ]


def test_upsert_writes_nothing_when_any_file_is_invalid(seed_root, cosmos, capsys):
    profile_path = seed_root / "account_profiles" / "example.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    (seed_root / "account_profiles" / "zz-mismatch.json").write_text(json.dumps({**profile, "id": "other"}), encoding="utf-8")

    assert seed_cosmos.main(["--endpoint", ENDPOINT]) == 1

    assert cosmos == []
    captured = capsys.readouterr()
    assert "upserted" not in captured.out
    assert "seed validation failed with 1 error(s); nothing was written" in captured.err
    assert profile["userId"] not in captured.err


@pytest.mark.parametrize("dry_run", [False, True])
def test_duplicate_old_definition_prevents_all_writes_and_client_construction(seed_root, monkeypatch, capsys, dry_run):
    monkeypatch.setattr(seed_cosmos, "CosmosClient", _refuse_construction)
    monkeypatch.setattr(seed_cosmos, "DefaultAzureCredential", _refuse_construction)
    definitions = seed_root / "ui_definitions"
    document = json.loads((definitions / "dashboard.json").read_text(encoding="utf-8"))
    old_document = {**document, "id": "dashboard:1", "version": "1"}
    (definitions / "a-old.json").write_text(json.dumps(old_document), encoding="utf-8")
    (definitions / "z-duplicate.json").write_text(json.dumps({**old_document, "revision": "different"}), encoding="utf-8")
    arguments = ["--dry-run"] if dry_run else ["--endpoint", ENDPOINT]

    assert seed_cosmos.main(arguments) == 1

    captured = capsys.readouterr()
    assert "would upsert" not in captured.out
    assert "upserted" not in captured.out
    assert "seed validation failed with 1 error(s); nothing was written" in captured.err
    assert "duplicates surface and version from seed/ui_definitions/a-old.json" in captured.err
