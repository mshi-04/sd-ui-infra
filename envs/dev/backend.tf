terraform {
  backend "azurerm" {
    key              = "dev/terraform.tfstate"
    container_name   = "tfstate"
    use_azuread_auth = true
    use_oidc         = true
  }
}
