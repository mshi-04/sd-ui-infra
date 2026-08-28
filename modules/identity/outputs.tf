output "api_client_id" {
  description = "access token の audience となる API アプリケーションの client id"
  value       = azuread_application.api.client_id
}

output "api_identifier_uri" {
  description = "API アプリケーションの identifier URI"
  value       = azuread_application_identifier_uri.api.identifier_uri
}

output "api_service_principal_object_id" {
  description = "API アプリケーションのサービスプリンシパルの object id"
  value       = azuread_service_principal.api.object_id
}

output "client_app_client_id" {
  description = "SPA クライアントの client id"
  value       = azuread_application.client.client_id
}

output "ui_schema_read_scope" {
  description = "UIスキーマ取得に必要な scope 名"
  value       = "UiSchema.Read"
}

output "app_role_values" {
  description = "定義済み app role の値"
  value       = keys(local.app_roles)
}

output "tenant_id" {
  description = "Entra ID のテナントID"
  value       = data.azuread_client_config.current.tenant_id
}
