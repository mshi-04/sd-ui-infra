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

variable "spa_redirect_uris" {
  description = "クライアントSPAのリダイレクトURI"
  type        = list(string)
  validation {
    condition     = alltrue([for uri in var.spa_redirect_uris : startswith(uri, "https://") || startswith(uri, "http://localhost")])
    error_message = "spa_redirect_uris は https または http://localhost で始まる必要があります。"
  }
}

variable "app_role_assignment_required" {
  description = "APIへのサインインに app role の割り当てを必須とするか。各環境で明示的に指定すること（dev: false, prod: true）"
  type        = bool
}
