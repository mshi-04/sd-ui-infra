output "tfstate_storage_account_name" {
  description = "Terraform state を保管する Storage Account 名"
  value       = azurerm_storage_account.tfstate.name
}

output "tfstate_container_name" {
  description = "Terraform state を保管するコンテナ名"
  value       = azurerm_storage_container.tfstate.name
}

output "tfstate_resource_group_name" {
  description = "Terraform state 用のリソースグループ名"
  value       = azurerm_resource_group.tfstate.name
}

output "workload_resource_group_names" {
  description = "環境ごとのワークロード用リソースグループ名"
  value       = { for env, rg in azurerm_resource_group.workload : env => rg.name }
}

output "ci_client_id" {
  description = "GitHub Actions が使う Entra ID アプリケーションの client id"
  value       = azuread_application.ci.client_id
}

output "tenant_id" {
  description = "Entra ID のテナントID"
  value       = data.azuread_client_config.current.tenant_id
}
