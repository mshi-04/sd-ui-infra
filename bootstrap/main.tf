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
  }
}

provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  resource_providers_to_register = [
    "Microsoft.AlertsManagement",
    "Microsoft.DocumentDB",
    "Microsoft.Insights",
    "Microsoft.OperationalInsights",
    "Microsoft.Storage",
    "Microsoft.Web",
  ]

  features {}
}

provider "azuread" {}

data "azuread_client_config" "current" {}

data "azuread_application_published_app_ids" "well_known" {}

data "azuread_service_principal" "msgraph" {
  client_id = data.azuread_application_published_app_ids.well_known.result["MicrosoftGraph"]
}

locals {
  plan_environment = "dev"
}

resource "azurerm_resource_group" "tfstate" {
  name     = "${var.project_name}-tfstate-rg"
  location = var.location

  tags = {
    Project   = var.project_name
    Purpose   = "terraform-state"
    ManagedBy = "Terraform"
  }
}

resource "azurerm_storage_account" "tfstate" {
  name                            = "${replace(var.project_name, "-", "")}tfstate"
  resource_group_name             = azurerm_resource_group.tfstate.name
  location                        = azurerm_resource_group.tfstate.location
  account_tier                    = "Standard"
  account_replication_type        = "GRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "tfstate" {
  for_each = toset(var.environments)

  name               = "tfstate-${each.key}"
  storage_account_id = azurerm_storage_account.tfstate.id
}

resource "azurerm_resource_group" "workload" {
  for_each = toset(var.environments)

  name     = "${var.project_name}-${each.value}-rg"
  location = var.location

  tags = {
    Project     = var.project_name
    Environment = each.value
    ManagedBy   = "Terraform"
  }
}

resource "azuread_application" "deploy" {
  for_each = toset(var.environments)

  display_name     = "${var.project_name}-deploy-${each.key}"
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "deploy" {
  for_each = azuread_application.deploy

  client_id = each.value.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "azuread_application_federated_identity_credential" "deploy" {
  for_each = azuread_application.deploy

  application_id = each.value.id
  display_name   = "github-environment-${each.key}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:environment:${each.key}"
}

resource "azurerm_role_assignment" "deploy_workload" {
  for_each = azurerm_resource_group.workload

  scope                = each.value.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.deploy[each.key].object_id
}

resource "azurerm_role_assignment" "deploy_rbac_admin" {
  for_each = azurerm_resource_group.workload

  scope                = each.value.id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azuread_service_principal.deploy[each.key].object_id

  condition_version = "2.0"
  condition         = <<-CONDITION
    (
      (
        !(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})
      )
      OR
      (
        @Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${join(", ", var.ci_assignable_role_definition_ids)}}
      )
    )
    AND
    (
      (
        !(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'})
      )
      OR
      (
        @Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${join(", ", var.ci_assignable_role_definition_ids)}}
      )
    )
  CONDITION
}

resource "azurerm_role_assignment" "operator_tfstate" {
  scope                = azurerm_storage_account.tfstate.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azuread_client_config.current.object_id
}

resource "azurerm_role_assignment" "deploy_tfstate" {
  for_each = azurerm_storage_container.tfstate

  scope                = each.value.resource_manager_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azuread_service_principal.deploy[each.key].object_id
}

resource "azuread_app_role_assignment" "deploy_graph_owned_by" {
  for_each = azuread_service_principal.deploy

  app_role_id         = data.azuread_service_principal.msgraph.app_role_ids["Application.ReadWrite.OwnedBy"]
  principal_object_id = each.value.object_id
  resource_object_id  = data.azuread_service_principal.msgraph.object_id
}

resource "azuread_application" "plan" {
  display_name     = "${var.project_name}-plan"
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "plan" {
  client_id = azuread_application.plan.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "azuread_application_federated_identity_credential" "plan" {
  application_id = azuread_application.plan.id
  display_name   = "github-pull-request"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:pull_request"
}

resource "azurerm_role_assignment" "plan_workload" {
  scope                = azurerm_resource_group.workload[local.plan_environment].id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.plan.object_id
}

resource "azurerm_role_assignment" "plan_tfstate" {
  scope                = azurerm_storage_container.tfstate[local.plan_environment].resource_manager_id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azuread_service_principal.plan.object_id
}
