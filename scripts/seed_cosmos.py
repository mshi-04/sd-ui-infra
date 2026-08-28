import argparse
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

SEED_ROOT = Path(__file__).resolve().parents[1] / "seed"
CONTAINER_BY_DIRECTORY = {
    "ui_definitions": "UI_DEFINITIONS_CONTAINER",
    "account_profiles": "ACCOUNT_PROFILES_CONTAINER",
}


def documents(directory: Path) -> Iterator[dict]:
    for path in sorted(directory.glob("*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))


def upsert_all(endpoint: str, database_name: str, dry_run: bool) -> int:
    database = CosmosClient(endpoint, credential=DefaultAzureCredential()).get_database_client(database_name)

    count = 0
    for directory_name, container_variable in CONTAINER_BY_DIRECTORY.items():
        directory = SEED_ROOT / directory_name
        container_name = os.environ.get(container_variable, directory_name)
        container = database.get_container_client(container_name)

        for document in documents(directory):
            if not dry_run:
                container.upsert_item(document)
            print(f"{'would upsert' if dry_run else 'upserted'} {container_name}/{document['id']}")
            count += 1

    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Upsert seed documents into Cosmos DB")
    parser.add_argument("--endpoint", default=os.environ.get("COSMOS_ENDPOINT"))
    parser.add_argument("--database", default=os.environ.get("COSMOS_DATABASE", "sdui"))
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    if not arguments.endpoint:
        parser.error("--endpoint or COSMOS_ENDPOINT is required")

    count = upsert_all(arguments.endpoint, arguments.database, arguments.dry_run)
    print(f"processed {count} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
