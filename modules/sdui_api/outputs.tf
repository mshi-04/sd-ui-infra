output "function_app_name" {
  description = "Function App 名"
  value       = azurerm_function_app_flex_consumption.api.name
}

output "function_app_default_hostname" {
  description = "Function App の既定ホスト名"
  value       = azurerm_function_app_flex_consumption.api.default_hostname
}

output "principal_id" {
  description = "Function App の system-assigned managed identity の principal id"
  value       = azurerm_function_app_flex_consumption.api.identity[0].principal_id
}

output "storage_account_name" {
  description = "Function App のデプロイ用 Storage Account 名"
  value       = azurerm_storage_account.api.name
}
