output "account_id" {
  description = "Cosmos DB アカウントのリソースID"
  value       = azurerm_cosmosdb_account.ui.id
}

output "account_name" {
  description = "Cosmos DB アカウント名"
  value       = azurerm_cosmosdb_account.ui.name
}

output "endpoint" {
  description = "Cosmos DB のエンドポイント"
  value       = azurerm_cosmosdb_account.ui.endpoint
}

output "database_name" {
  description = "Cosmos DB のデータベース名"
  value       = azurerm_cosmosdb_sql_database.ui.name
}

output "ui_definitions_container_name" {
  description = "UI定義コンテナ名"
  value       = azurerm_cosmosdb_sql_container.ui_definitions.name
}

output "account_profiles_container_name" {
  description = "アカウントプロファイルコンテナ名"
  value       = azurerm_cosmosdb_sql_container.account_profiles.name
}
