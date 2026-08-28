terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.58.0"
    }
  }
}

resource "azurerm_log_analytics_workspace" "sdui" {
  name                = "${var.project_name}-logs-${var.env}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_in_days
}

resource "azurerm_application_insights" "sdui" {
  name                = "${var.project_name}-appi-${var.env}"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.sdui.id
  application_type    = "web"
  sampling_percentage = var.sampling_percentage
}
