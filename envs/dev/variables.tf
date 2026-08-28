variable "subscription_id" {
  description = "デプロイ先のサブスクリプションID"
  type        = string
}

variable "project_name" {
  description = "プロジェクト名"
  type        = string
  default     = "sd-ui"
}

variable "spa_redirect_uris" {
  description = "クライアントSPAのリダイレクトURI"
  type        = list(string)
}

variable "allowed_origins" {
  description = "UIスキーマAPIを呼び出すクライアントのオリジン"
  type        = list(string)
}
