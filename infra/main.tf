provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

data "azurerm_resource_group" "rg" {
  name = var.resource_group_name
}

# -----------------------
# Storage + Table (state)
# -----------------------
resource "azurerm_storage_account" "sa" {
  name                     = var.storage_account_name
  resource_group_name      = data.azurerm_resource_group.rg.name
  location                 = data.azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_table" "state" {
  name                 = var.state_table_name
  storage_account_name = azurerm_storage_account.sa.name
}

# -----------------------
# App Service (2 régions)
# -----------------------
resource "azurerm_service_plan" "plan_a" {
  name                = "${var.prefix}-plan-a"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.region_a
  os_type             = "Linux"
  sku_name            = "B1"
}

resource "azurerm_service_plan" "plan_b" {
  name                = "${var.prefix}-plan-b"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.region_b
  os_type             = "Linux"
  sku_name            = "B1"
}

# WebApp A (container simple)
resource "azurerm_linux_web_app" "web_a" {
  name                = "${var.prefix}-web-a"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.region_a
  service_plan_id     = azurerm_service_plan.plan_a.id

  site_config {
    application_stack {
      docker_image_name   = "mcr.microsoft.com/azuredocs/aci-helloworld"
      docker_registry_url = "https://mcr.microsoft.com"
    }
  }

  app_settings = {
    WEBSITES_PORT = "80"
  }
}

# WebApp B (même image)
resource "azurerm_linux_web_app" "web_b" {
  name                = "${var.prefix}-web-b"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = var.region_b
  service_plan_id     = azurerm_service_plan.plan_b.id

  site_config {
    application_stack {
      docker_image_name   = "mcr.microsoft.com/azuredocs/aci-helloworld"
      docker_registry_url = "https://mcr.microsoft.com"
    }
  }

  app_settings = {
    WEBSITES_PORT = "80"
  }
}

# -----------------------
# Azure DNS (zone + cname)
# -----------------------
resource "azurerm_dns_zone" "zone" {
  name                = var.dns_zone_name
  resource_group_name = data.azurerm_resource_group.rg.name
}

# CNAME app.<zone> -> WebApp A au départ
resource "azurerm_dns_cname_record" "app" {
  name                = var.dns_record_name          # ex: "app"
  zone_name           = azurerm_dns_zone.zone.name
  resource_group_name = data.azurerm_resource_group.rg.name
  ttl                 = 30
  record              = azurerm_linux_web_app.web_a.default_hostname
}

# -----------------------
# Function App
# -----------------------
resource "azurerm_service_plan" "func_plan" {
  name                = "${var.function_app_name}-plan"
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = data.azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "EP1"
}

resource "azurerm_linux_function_app" "func" {
  name                = var.function_app_name
  resource_group_name = data.azurerm_resource_group.rg.name
  location            = data.azurerm_resource_group.rg.location

  service_plan_id            = azurerm_service_plan.func_plan.id
  storage_account_name       = azurerm_storage_account.sa.name
  storage_account_access_key = azurerm_storage_account.sa.primary_access_key

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME = "python"
    AzureWebJobsStorage      = azurerm_storage_account.sa.primary_connection_string

    STATE_TABLE_NAME = var.state_table_name
    COOLDOWN_MINUTES = tostring(var.cooldown_minutes)

    # URLs “réelles” des 2 régions (utilisées par health_check)
    PRIMARY_APP_URL   = "https://${azurerm_linux_web_app.web_a.default_hostname}"
    SECONDARY_APP_URL = "https://${azurerm_linux_web_app.web_b.default_hostname}"

    # DNS cible de bascule (CNAME)
    SUBSCRIPTION_ID     = var.subscription_id
    RESOURCE_GROUP_NAME = data.azurerm_resource_group.rg.name
    DNS_ZONE_NAME       = azurerm_dns_zone.zone.name
    DNS_RECORD_NAME     = var.dns_record_name
    DNS_TTL             = "30"
    ARM_API_VERSION     = "2018-05-01"

    # Service Principal (pour ARM DNS)
    AZURE_TENANT_ID     = var.azure_tenant_id
    AZURE_CLIENT_ID     = var.azure_client_id
    AZURE_CLIENT_SECRET = var.azure_client_secret
  }

  zip_deploy_file = "${path.module}/${var.functions_zip_path}"
}

resource "azurerm_logic_app_workflow" "failover_logic" {
  name                = "${var.prefix}-logicapp"
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name
}

locals {
  function_base_url = "https://${azurerm_linux_function_app.func.default_hostname}/api"
}

resource "azurerm_resource_group_template_deployment" "logicapp" {
  name                = "${var.prefix}-logicapp-deploy"
  resource_group_name = data.azurerm_resource_group.rg.name
  deployment_mode     = "Incremental"

  template_content = file("${path.module}/templates/logicapp.arm.json")

  parameters_content = jsonencode({
    logicAppName = { value = "${var.prefix}-orchestrator" }
    location     = { value = data.azurerm_resource_group.rg.location }

    functionBaseUrl  = { value = local.function_base_url }
    healthKey   = { value = data.azurerm_function_app_host_keys.func_keys.default_function_key }
    failoverKey = { value = data.azurerm_function_app_host_keys.func_keys.default_function_key }
    intervalMinutes  = { value = var.logicapp_interval_minutes }
  })

  depends_on = [azurerm_linux_function_app.func,data.azurerm_function_app_host_keys.func_keys]
}

data "azurerm_function_app_host_keys" "func_keys" {
  name                = azurerm_linux_function_app.func.name
  resource_group_name = data.azurerm_resource_group.rg.name

  depends_on = [azurerm_linux_function_app.func]
}



