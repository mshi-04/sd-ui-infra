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

variable "log_retention_in_days" {
  description = "ログ保持日数。各環境で明示的に指定すること（dev: 30, prod: 90）"
  type        = number
  validation {
    condition     = var.log_retention_in_days >= 30 && var.log_retention_in_days <= 730
    error_message = "log_retention_in_days は 30 から 730 の範囲で指定してください。"
  }
}

variable "sampling_percentage" {
  description = "Application Insights のサンプリング率"
  type        = number
  default     = 100
}
