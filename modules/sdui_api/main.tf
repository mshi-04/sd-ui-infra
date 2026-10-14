terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.58.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0"
    }
  }
}

locals {
  storage_account_name    = substr("${replace(var.project_name, "-", "")}api${var.env}", 0, 24)
  deployment_container    = "deployments"
  cosmos_data_reader_role = "${var.cosmos_account_id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000001"
}

resource "random_uuid" "cosmos_role_assignment" {}

resource "azurerm_storage_account" "api" {
  name                            = local.storage_account_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
}

resource "azurerm_storage_container" "deployments" {
  name               = local.deployment_container
  storage_account_id = azurerm_storage_account.api.id
}

resource "azurerm_service_plan" "api" {
  name                = "${var.project_name}-plan-${var.env}"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "FC1"
}

resource "azurerm_function_app_flex_consumption" "api" {
  name                        = "${var.project_name}-api-${var.env}"
  resource_group_name         = var.resource_group_name
  location                    = var.location
  service_plan_id             = azurerm_service_plan.api.id
  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.api.primary_blob_endpoint}${azurerm_storage_container.deployments.name}"
  storage_authentication_type = "SystemAssignedIdentity"
  runtime_name                = "python"
  runtime_version             = "3.14"
  instance_memory_in_mb       = var.instance_memory_in_mb
  maximum_instance_count      = var.maximum_instance_count
  https_only                  = true

  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_insights_connection_string = var.application_insights_connection_string

    dynamic "cors" {
      for_each = length(var.allowed_origins) > 0 ? [1] : []

      content {
        allowed_origins     = var.allowed_origins
        support_credentials = false
      }
    }
  }

  app_settings = {
    AzureWebJobsStorage__accountName = azurerm_storage_account.api.name
    ENTRA_TENANT_ID                  = var.tenant_id
    ENTRA_API_CLIENT_ID              = var.api_client_id
    REQUIRED_SCOPE                   = var.required_scope
    ROLE_ENTITLEMENTS                = jsonencode(var.role_entitlements)
    COSMOS_ENDPOINT                  = var.cosmos_endpoint
    COSMOS_DATABASE                  = var.cosmos_database_name
    UI_DEFINITIONS_CONTAINER         = var.ui_definitions_container_name
    ACCOUNT_PROFILES_CONTAINER       = var.account_profiles_container_name
    UI_CACHE_MAX_AGE_SECONDS         = tostring(var.ui_cache_max_age_seconds)
  }
}

resource "azurerm_role_assignment" "api_storage_blob" {
  scope                = azurerm_storage_account.api.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_function_app_flex_consumption.api.identity[0].principal_id
}

resource "azurerm_cosmosdb_sql_role_assignment" "api_reader" {
  name                = random_uuid.cosmos_role_assignment.result
  resource_group_name = var.resource_group_name
  account_name        = var.cosmos_account_name
  role_definition_id  = local.cosmos_data_reader_role
  principal_id        = azurerm_function_app_flex_consumption.api.identity[0].principal_id
  scope               = var.cosmos_account_id
}

resource "azurerm_monitor_diagnostic_setting" "api" {
  name                       = "${var.project_name}-api-${var.env}"
  target_resource_id         = azurerm_function_app_flex_consumption.api.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "FunctionAppLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
