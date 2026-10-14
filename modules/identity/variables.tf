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

variable "public_client_redirect_uris" {
  description = "モバイルクライアントのリダイレクトURI。MSAL Android は msauth://<package>/<signature-hash> 形式"
  type        = list(string)
  validation {
    condition     = alltrue([for uri in var.public_client_redirect_uris : startswith(uri, "msauth://") || startswith(uri, "http://localhost")])
    error_message = "public_client_redirect_uris は msauth:// または http://localhost で始まる必要があります。"
  }
}

variable "app_role_assignment_required" {
  description = "APIへのサインインに app role の割り当てを必須とするか。各環境で明示的に指定すること（dev: false, prod: true）"
  type        = bool
}

variable "app_roles" {
  description = "API アプリが公開する app role と、role が付与する entitlement"
  type = map(object({
    display_name = string
    description  = string
    entitlements = list(string)
  }))
}

variable "owner_object_ids" {
  description = "Entra ID のアプリ登録とサービスプリンシパルの owner の object id。Application.ReadWrite.OwnedBy で管理するため、実行主体を含める"
  type        = list(string)
  validation {
    condition     = length(var.owner_object_ids) >= 1 && alltrue([for id in var.owner_object_ids : can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", id))])
    error_message = "owner_object_ids には UUID を1つ以上指定してください。"
  }
}

variable "pre_authorized_client_ids" {
  description = "同意なしで scope を要求できるクライアントの client id。運用確認用に dev でのみ指定する"
  type        = list(string)
  default     = []
}
