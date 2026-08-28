terraform {
  backend "azurerm" {
    key              = "prod/terraform.tfstate"
    container_name   = "tfstate"
    use_azuread_auth = true
    use_oidc         = true
  }
}
