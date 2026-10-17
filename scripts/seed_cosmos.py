import argparse
import os
import sys
from collections.abc import Sequence

from azure.cosmos import CosmosClient, DatabaseProxy
from azure.identity import DefaultAzureCredential

from seed_validation import SEED_ROOT, SeedDocument, SeedReport, validate_seed

CONTAINER_BY_DIRECTORY = {
    "ui_definitions": "UI_DEFINITIONS_CONTAINER",
    "account_profiles": "ACCOUNT_PROFILES_CONTAINER",
}


def container_name(directory: str) -> str:
    return os.environ.get(CONTAINER_BY_DIRECTORY[directory], directory)


def print_findings(report: SeedReport) -> None:
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"error: {error}", file=sys.stderr)


def plan_upserts(documents: Sequence[SeedDocument]) -> int:
    for document in documents:
        print(f"would upsert {document.file} into {container_name(document.directory)}")
    return len(documents)


def upsert_all(database: DatabaseProxy, documents: Sequence[SeedDocument]) -> int:
    for document in documents:
        name = container_name(document.directory)
        database.get_container_client(name).upsert_item(dict(document.content))
        print(f"upserted {document.file} into {name}")
    return len(documents)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate seed documents and upsert them into Cosmos DB")
    parser.add_argument("--endpoint", default=os.environ.get("COSMOS_ENDPOINT"))
    parser.add_argument("--database", default=os.environ.get("COSMOS_DATABASE", "sdui"))
    parser.add_argument("--dry-run", action="store_true", help="validate and list planned upserts without connecting to Azure")
    arguments = parser.parse_args(argv)

    if not arguments.dry_run and not arguments.endpoint:
        parser.error("--endpoint or COSMOS_ENDPOINT is required unless --dry-run is given")

    report = validate_seed(SEED_ROOT)
    print_findings(report)
    if report.errors:
        print(f"seed validation failed with {len(report.errors)} error(s); nothing was written", file=sys.stderr)
        return 1

    if arguments.dry_run:
        count = plan_upserts(report.documents)
        print(f"validated {count} documents; dry run wrote nothing")
        return 0

    database = CosmosClient(arguments.endpoint, credential=DefaultAzureCredential()).get_database_client(arguments.database)
    count = upsert_all(database, report.documents)
    print(f"upserted {count} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
