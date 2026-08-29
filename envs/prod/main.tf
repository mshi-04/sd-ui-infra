terraform {
  required_version = "1.15.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "4.58.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "3.7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.7.2"
    }
  }
}

provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  features {}
}

provider "azuread" {}

locals {
  env       = "prod"
  app_roles = jsondecode(file("${path.module}/../../config/app_roles.json"))
}

data "azurerm_resource_group" "sdui" {
  name = "${var.project_name}-${local.env}-rg"
}

module "identity" {
  source = "../../modules/identity"

  env                          = local.env
  project_name                 = var.project_name
  app_roles                    = local.app_roles
  app_role_assignments         = var.app_role_assignments
  public_client_redirect_uris  = var.public_client_redirect_uris
  pre_authorized_client_ids    = var.pre_authorized_client_ids
  app_role_assignment_required = true
}

module "ui_store" {
  source = "../../modules/ui_store"

  env                    = local.env
  project_name           = var.project_name
  resource_group_name    = data.azurerm_resource_group.sdui.name
  location               = data.azurerm_resource_group.sdui.location
  backup_type            = "Continuous"
  continuous_backup_tier = "Continuous7Days"
}

module "observability" {
  source = "../../modules/observability"

  env                   = local.env
  project_name          = var.project_name
  resource_group_name   = data.azurerm_resource_group.sdui.name
  location              = data.azurerm_resource_group.sdui.location
  log_retention_in_days = 90
}

module "sdui_api" {
  source = "../../modules/sdui_api"

  env                 = local.env
  project_name        = var.project_name
  resource_group_name = data.azurerm_resource_group.sdui.name
  location            = data.azurerm_resource_group.sdui.location

  tenant_id         = module.identity.tenant_id
  api_client_id     = module.identity.api_client_id
  required_scope    = module.identity.ui_schema_read_scope
  role_entitlements = module.identity.role_entitlements

  cosmos_account_id               = module.ui_store.account_id
  cosmos_account_name             = module.ui_store.account_name
  cosmos_endpoint                 = module.ui_store.endpoint
  cosmos_database_name            = module.ui_store.database_name
  ui_definitions_container_name   = module.ui_store.ui_definitions_container_name
  account_profiles_container_name = module.ui_store.account_profiles_container_name

  application_insights_connection_string = module.observability.application_insights_connection_string
  log_analytics_workspace_id             = module.observability.workspace_id

  allowed_origins        = var.allowed_origins
  maximum_instance_count = 100
}
