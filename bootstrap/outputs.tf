output "tfstate_storage_account_name" {
  description = "Terraform state を保管する Storage Account 名"
  value       = azurerm_storage_account.tfstate.name
}

output "tfstate_container_names" {
  description = "環境ごとの Terraform state 用コンテナ名"
  value       = { for env, container in azurerm_storage_container.tfstate : env => container.name }
}

output "tfstate_resource_group_name" {
  description = "Terraform state 用のリソースグループ名"
  value       = azurerm_resource_group.tfstate.name
}

output "workload_resource_group_names" {
  description = "環境ごとのワークロード用リソースグループ名"
  value       = { for env, rg in azurerm_resource_group.workload : env => rg.name }
}

output "deploy_client_ids" {
  description = "環境ごとのデプロイ用 Entra ID アプリケーションの client id"
  value       = { for env, app in azuread_application.deploy : env => app.client_id }
}

output "deploy_service_principal_object_ids" {
  description = "環境ごとのデプロイ用サービスプリンシパルの object id。各環境の app_owner_object_id に使う"
  value       = { for env, sp in azuread_service_principal.deploy : env => sp.object_id }
}

output "plan_client_id" {
  description = "PR の plan 用 Entra ID アプリケーションの client id"
  value       = azuread_application.plan.client_id
}

output "tenant_id" {
  description = "Entra ID のテナントID"
  value       = data.azuread_client_config.current.tenant_id
}
