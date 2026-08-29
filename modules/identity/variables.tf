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
