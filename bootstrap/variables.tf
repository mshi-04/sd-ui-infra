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

variable "ci_assignable_role_definition_ids" {
  description = "デプロイ用 ID が自環境のリソースグループ内で割り当てを許可される組み込みロールの定義ID"
  type        = list(string)
  default = [
    # Storage Blob Data Owner
    "b7e6dc6d-f1e8-4753-8033-0f276bb0955b",
    # Storage Blob Data Contributor
    "ba92f5b4-2d11-453d-a403-e96b0029c9fe",
  ]
}
