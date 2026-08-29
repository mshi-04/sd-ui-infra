variable "subscription_id" {
  description = "デプロイ先のサブスクリプションID"
  type        = string
}

variable "project_name" {
  description = "プロジェクト名"
  type        = string
  default     = "sd-ui"
}

variable "public_client_redirect_uris" {
  description = "Android クライアントのリダイレクトURI"
  type        = list(string)
}

variable "allowed_origins" {
  description = "UIスキーマAPIを呼び出すブラウザクライアントのオリジン。Android のみの場合は空にする"
  type        = list(string)
}
