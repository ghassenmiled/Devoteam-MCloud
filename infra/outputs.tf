

output "webapp_a_url" {
  value = "https://${azurerm_linux_web_app.web_a.default_hostname}"
}

output "webapp_b_url" {
  value = "https://${azurerm_linux_web_app.web_b.default_hostname}"
}

output "dns_fqdn" {
  value = "${var.dns_record_name}.${azurerm_dns_zone.zone.name}"
}

output "function_base_url" {
  value = local.function_base_url
}

output "logic_app_name" {
  value = "${var.prefix}-orchestrator"
}
