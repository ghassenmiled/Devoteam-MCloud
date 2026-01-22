provider "azurerm" {
  features {}
}

locals {
  table_name = "failoverstate" # ✅ no underscore
  function_base_url = "https://${azurerm_linux_function_app.func.default_hostname}/api"
}

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_storage_account" "sa" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_table" "state" {
  name                 = local.table_name
  storage_account_name = azurerm_storage_account.sa.name
}

resource "azurerm_service_plan" "plan" {
  name                = "${var.function_app_name}-plan"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "Y1"
}

resource "azurerm_linux_function_app" "func" {
  name                = var.function_app_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  service_plan_id            = azurerm_service_plan.plan.id
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

    STATE_TABLE_NAME   = local.table_name
    PRIMARY_ENDPOINT   = var.primary_endpoint
    SECONDARY_ENDPOINT = var.secondary_endpoint
    COOLDOWN_MINUTES   = tostring(var.cooldown_minutes)
  }

  zip_deploy_file = var.functions_zip_path
}

# ✅ Deploy Logic App via ARM template (works with azurerm v4)
resource "azurerm_resource_group_template_deployment" "logicapp" {
  name                = "${var.function_app_name}-logicapp-deploy"
  resource_group_name = azurerm_resource_group.rg.name
  deployment_mode     = "Incremental"

  template_content = file("${path.module}/logicapp.arm.json")

  parameters_content = jsonencode({
    logicAppName = { value = "${var.function_app_name}-orchestrator" }
    location     = { value = azurerm_resource_group.rg.location }

    functionBaseUrl = { value = local.function_base_url }
    healthKey       = { value = var.health_function_key }
    failoverKey     = { value = var.failover_function_key }
    intervalMinutes = { value = var.logicapp_interval_minutes }
  })

  depends_on = [azurerm_linux_function_app.func]
}
