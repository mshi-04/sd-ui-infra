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

variable "app_role_assignments" {
  description = "ユーザーの object id と、割り当てる app role の対応"
  type        = map(list(string))
  default     = {}
  validation {
    condition     = alltrue([for roles in values(var.app_role_assignments) : alltrue([for role in roles : contains(keys(var.app_roles), role)])])
    error_message = "app_role_assignments には app_roles に定義された role のみ指定できます。"
  }
}
