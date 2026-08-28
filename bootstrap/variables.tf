variable "subscription_id" {
  description = "デプロイ先のサブスクリプションID"
  type        = string
}

variable "project_name" {
  description = "プロジェクト名"
  type        = string
  default     = "sd-ui"
}

variable "location" {
  description = "Azure リージョン"
  type        = string
  default     = "japaneast"
}

variable "environments" {
  description = "作成する環境名"
  type        = list(string)
  default     = ["dev", "prod"]
}

variable "github_repository" {
  description = "workload identity federation を許可する GitHub リポジトリ（owner/name）"
  type        = string
  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "github_repository は owner/name 形式で指定してください。"
  }
}

variable "assignable_role_definition_ids" {
  description = "CI が割り当て可能なロール定義IDのGUID。カンマ区切りの引用符付き文字列として condition へ埋め込む"
  type        = string
  default     = "'ba92f5b4-2d11-453d-a403-e96b0029c9fe','2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'"
}
