output "workspace_id" {
  description = "Log Analytics workspace のリソースID"
  value       = azurerm_log_analytics_workspace.sdui.id
}

output "application_insights_connection_string" {
  description = "Application Insights の接続文字列"
  value       = azurerm_application_insights.sdui.connection_string
  sensitive   = true
}
