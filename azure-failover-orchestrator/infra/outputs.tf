output "function_base_url" {
  value = "https://${azurerm_linux_function_app.func.default_hostname}/api"
}

output "logic_app_name" {
  value = "${var.function_app_name}-orchestrator"
}

output "storage_table_name" {
  value = azurerm_storage_table.state.name
}
