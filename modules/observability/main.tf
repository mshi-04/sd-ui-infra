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

locals {
  alerts_enabled = length(var.alert_email_addresses) > 0
}

resource "azurerm_monitor_action_group" "server_errors" {
  count = local.alerts_enabled ? 1 : 0

  name                = "${var.project_name}-ag-${var.env}"
  resource_group_name = var.resource_group_name
  short_name          = "${var.project_name}-${var.env}"

  dynamic "email_receiver" {
    for_each = var.alert_email_addresses
    content {
      name          = "email-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "server_errors" {
  count = local.alerts_enabled ? 1 : 0

  name                 = "${var.project_name}-api-5xx-${var.env}"
  resource_group_name  = var.resource_group_name
  location             = var.location
  scopes               = [azurerm_application_insights.sdui.id]
  severity             = 2
  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"

  criteria {
    query                   = "requests | where toint(resultCode) >= 500"
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = var.server_error_alert_threshold

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.server_errors[0].id]
  }
}
