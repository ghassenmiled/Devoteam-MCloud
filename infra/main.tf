provider "azurerm" {
  features {}
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
  name                 = "failover_state"
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
    "FUNCTIONS_WORKER_RUNTIME" = "python"
    "AzureWebJobsStorage"      = azurerm_storage_account.sa.primary_connection_string

    "STATE_TABLE_NAME"   = "failover_state"
    "PRIMARY_ENDPOINT"   = var.primary_endpoint
    "SECONDARY_ENDPOINT" = var.secondary_endpoint
    "COOLDOWN_MINUTES"   = tostring(var.cooldown_minutes)
  }

  zip_deploy_file = var.functions_zip_path
}

resource "azurerm_logic_app_workflow" "orchestrator" {
  name                = "${var.function_app_name}-orchestrator"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  definition = jsondecode(
    templatefile("${path.module}/logicapp.json.tftpl", {
      function_base_url = "https://${azurerm_linux_function_app.func.default_hostname}/api"
      health_key        = var.health_function_key
      failover_key      = var.failover_function_key
      interval_minutes  = var.logicapp_interval_minutes
    })
  )
}
