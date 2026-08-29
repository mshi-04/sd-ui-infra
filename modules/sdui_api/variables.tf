variable "env" {
  description = "環境名"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env は dev または prod を指定してください。"
  }
}

variable "project_name" {
  description = "プロジェクト名"
  type        = string
  default     = "sd-ui"
}

variable "resource_group_name" {
  description = "リソースグループ名"
  type        = string
}

variable "location" {
  description = "Azure リージョン"
  type        = string
}

variable "tenant_id" {
  description = "Entra ID のテナントID"
  type        = string
}

variable "api_client_id" {
  description = "access token の audience となる API アプリケーションの client id"
  type        = string
}

variable "required_scope" {
  description = "UIスキーマ取得に必要な scope 名"
  type        = string
  default     = "UiSchema.Read"
}

variable "role_entitlements" {
  description = "app role が付与する entitlement"
  type        = map(list(string))
}

variable "cosmos_account_id" {
  description = "Cosmos DB アカウントのリソースID"
  type        = string
}

variable "cosmos_account_name" {
  description = "Cosmos DB アカウント名"
  type        = string
}

variable "cosmos_endpoint" {
  description = "Cosmos DB のエンドポイント"
  type        = string
}

variable "cosmos_database_name" {
  description = "Cosmos DB のデータベース名"
  type        = string
}

variable "ui_definitions_container_name" {
  description = "UI定義コンテナ名"
  type        = string
}

variable "account_profiles_container_name" {
  description = "アカウントプロファイルコンテナ名"
  type        = string
}

variable "application_insights_connection_string" {
  description = "Application Insights の接続文字列"
  type        = string
  sensitive   = true
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace のリソースID"
  type        = string
}

variable "allowed_origins" {
  description = "UIスキーマAPIを呼び出すブラウザクライアントのオリジン。ネイティブアプリのみの場合は空にする"
  type        = list(string)
}

variable "instance_memory_in_mb" {
  description = "Flex Consumption のインスタンスメモリ"
  type        = number
  default     = 2048
  validation {
    condition     = contains([512, 2048, 4096], var.instance_memory_in_mb)
    error_message = "instance_memory_in_mb は 512, 2048, 4096 のいずれかを指定してください。"
  }
}

variable "maximum_instance_count" {
  description = "スケールアウト上限。各環境で明示的に指定すること（dev: 40, prod: 100）"
  type        = number
}

variable "ui_cache_max_age_seconds" {
  description = "UIスキーマレスポンスの Cache-Control max-age"
  type        = number
  default     = 60
}
