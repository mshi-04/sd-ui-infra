terraform {
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 3.7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0"
    }
  }
}

data "azuread_client_config" "current" {}

resource "random_uuid" "ui_schema_read" {}

resource "random_uuid" "app_role" {
  for_each = var.app_roles
}

resource "azuread_application" "api" {
  display_name     = "${var.project_name}-api-${var.env}"
  sign_in_audience = "AzureADMyOrg"
  owners           = var.owner_object_ids

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = random_uuid.ui_schema_read.result
      value                      = "UiSchema.Read"
      type                       = "User"
      enabled                    = true
      admin_consent_display_name = "Read the server-driven UI schema"
      admin_consent_description  = "Allows the client to read the server-driven UI schema on behalf of the signed-in user."
      user_consent_display_name  = "Read your UI schema"
      user_consent_description   = "Allows the client to read the UI resolved for your account."
    }
  }

  dynamic "app_role" {
    for_each = var.app_roles

    content {
      id                   = random_uuid.app_role[app_role.key].result
      value                = app_role.key
      allowed_member_types = ["User"]
      enabled              = true
      display_name         = app_role.value.display_name
      description          = app_role.value.description
    }
  }

  lifecycle {
    ignore_changes = [identifier_uris]
  }
}

resource "azuread_application_identifier_uri" "api" {
  application_id = azuread_application.api.id
  identifier_uri = "api://${azuread_application.api.client_id}"
}

resource "azuread_service_principal" "api" {
  client_id                    = azuread_application.api.client_id
  app_role_assignment_required = var.app_role_assignment_required
  owners                       = var.owner_object_ids
}

resource "azuread_application" "client" {
  display_name     = "${var.project_name}-client-${var.env}"
  sign_in_audience = "AzureADMyOrg"
  owners           = var.owner_object_ids

  public_client {
    redirect_uris = var.public_client_redirect_uris
  }

  required_resource_access {
    resource_app_id = azuread_application.api.client_id

    resource_access {
      id   = random_uuid.ui_schema_read.result
      type = "Scope"
    }
  }
}

resource "azuread_service_principal" "client" {
  client_id = azuread_application.client.client_id
  owners    = var.owner_object_ids
}

resource "azuread_application_pre_authorized" "client" {
  application_id       = azuread_application.api.id
  authorized_client_id = azuread_application.client.client_id
  permission_ids       = [random_uuid.ui_schema_read.result]
}

resource "azuread_application_pre_authorized" "additional" {
  for_each = toset(var.pre_authorized_client_ids)

  application_id       = azuread_application.api.id
  authorized_client_id = each.value
  permission_ids       = [random_uuid.ui_schema_read.result]
}
