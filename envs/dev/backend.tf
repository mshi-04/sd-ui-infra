terraform {
  backend "azurerm" {
    key              = "dev/terraform.tfstate"
    container_name   = "tfstate-dev"
    use_azuread_auth = true
    use_oidc         = true
  }
}
