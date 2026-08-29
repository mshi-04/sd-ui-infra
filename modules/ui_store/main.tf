terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.58.0"
    }
  }
}

resource "azurerm_cosmosdb_account" "ui" {
  name                          = "${var.project_name}-cosmos-${var.env}"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  offer_type                    = "Standard"
  kind                          = "GlobalDocumentDB"
  local_authentication_disabled = true
  free_tier_enabled             = false
  public_network_access_enabled = true
  minimal_tls_version           = "Tls12"

  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }

  backup {
    type                = var.backup_type
    tier                = var.backup_type == "Continuous" ? var.continuous_backup_tier : null
    interval_in_minutes = var.backup_type == "Periodic" ? var.periodic_backup_interval_in_minutes : null
    retention_in_hours  = var.backup_type == "Periodic" ? var.periodic_backup_retention_in_hours : null
    storage_redundancy  = var.backup_type == "Periodic" ? var.periodic_backup_storage_redundancy : null
  }
}

resource "azurerm_cosmosdb_sql_database" "ui" {
  name                = var.database_name
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.ui.name
}

resource "azurerm_cosmosdb_sql_container" "ui_definitions" {
  name                  = "ui_definitions"
  resource_group_name   = var.resource_group_name
  account_name          = azurerm_cosmosdb_account.ui.name
  database_name         = azurerm_cosmosdb_sql_database.ui.name
  partition_key_paths   = ["/surface"]
  partition_key_version = 2

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

resource "azurerm_cosmosdb_sql_container" "account_profiles" {
  name                  = "account_profiles"
  resource_group_name   = var.resource_group_name
  account_name          = azurerm_cosmosdb_account.ui.name
  database_name         = azurerm_cosmosdb_sql_database.ui.name
  partition_key_paths   = ["/userId"]
  partition_key_version = 2

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}
