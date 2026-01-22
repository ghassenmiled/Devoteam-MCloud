output "function_base_url" {
  value = "https://${azurerm_linux_function_app.func.default_hostname}/api"
}

output "logic_app_name" {
  value = azurerm_logic_app_workflow.orchestrator.name
}

output "storage_table_name" {
  value = azurerm_storage_table.state.name
}
