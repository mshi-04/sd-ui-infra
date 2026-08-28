output "api_base_url" {
  description = "UIスキーマAPIのベースURL"
  value       = "https://${module.sdui_api.function_app_default_hostname}/api"
}

output "function_app_name" {
  description = "Function App 名"
  value       = module.sdui_api.function_app_name
}

output "entra_tenant_id" {
  description = "Entra ID のテナントID"
  value       = module.identity.tenant_id
}

output "entra_api_client_id" {
  description = "access token の audience となる API アプリケーションの client id"
  value       = module.identity.api_client_id
}

output "entra_client_app_client_id" {
  description = "SPA クライアントの client id"
  value       = module.identity.client_app_client_id
}

output "cosmos_endpoint" {
  description = "Cosmos DB のエンドポイント"
  value       = module.ui_store.endpoint
}
