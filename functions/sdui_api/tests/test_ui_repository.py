from unittest.mock import Mock

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

import ui_repository
from constants import Settings
from models import AccountProfile


def test_missing_cosmos_profile_becomes_empty_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    container = Mock()
    container.read_item.side_effect = CosmosResourceNotFoundError(message="profile missing")
    monkeypatch.setattr(ui_repository, "_container", Mock(return_value=container))
    settings = Settings(
        tenant_id="tenant",
        api_client_id="audience",
        required_scope="UiSchema.Read",
        cosmos_endpoint="https://example.invalid/",
        cosmos_database="test-db",
        ui_definitions_container="ui-definitions",
        account_profiles_container="account-profiles",
        cache_max_age_seconds=60,
        role_entitlements={},
    )

    profile = ui_repository.fetch_profile(settings, "missing-user")

    assert profile == AccountProfile.empty("missing-user")
    container.read_item.assert_called_once_with(item="missing-user", partition_key="missing-user")
