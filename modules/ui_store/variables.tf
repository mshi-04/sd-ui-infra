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

variable "database_name" {
  description = "Cosmos DB のデータベース名"
  type        = string
  default     = "sdui"
}

variable "backup_type" {
  description = "バックアップ方式。各環境で明示的に指定すること（dev: Periodic, prod: Continuous）"
  type        = string
  validation {
    condition     = contains(["Periodic", "Continuous"], var.backup_type)
    error_message = "backup_type は Periodic または Continuous を指定してください。"
  }
}

variable "continuous_backup_tier" {
  description = "Continuous バックアップの保持期間"
  type        = string
  default     = "Continuous7Days"
  validation {
    condition     = contains(["Continuous7Days", "Continuous30Days"], var.continuous_backup_tier)
    error_message = "continuous_backup_tier は Continuous7Days または Continuous30Days を指定してください。"
  }
}

variable "periodic_backup_interval_in_minutes" {
  description = "Periodic バックアップの取得間隔"
  type        = number
  default     = 240
  validation {
    condition     = var.periodic_backup_interval_in_minutes >= 60 && var.periodic_backup_interval_in_minutes <= 1440
    error_message = "periodic_backup_interval_in_minutes は 60 から 1440 の範囲で指定してください。"
  }
}

variable "periodic_backup_retention_in_hours" {
  description = "Periodic バックアップの保持時間"
  type        = number
  default     = 8
  validation {
    condition     = var.periodic_backup_retention_in_hours >= 8 && var.periodic_backup_retention_in_hours <= 720
    error_message = "periodic_backup_retention_in_hours は 8 から 720 の範囲で指定してください。"
  }
}

variable "periodic_backup_storage_redundancy" {
  description = "Periodic バックアップの冗長性"
  type        = string
  default     = "Local"
  validation {
    condition     = contains(["Geo", "Local", "Zone"], var.periodic_backup_storage_redundancy)
    error_message = "periodic_backup_storage_redundancy は Geo, Local, Zone のいずれかを指定してください。"
  }
}
