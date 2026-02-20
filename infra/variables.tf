variable "subscription_id" { type = string }
variable "resource_group_name" { type = string }

variable "prefix" { type = string }

variable "function_app_name" { type = string }
variable "functions_zip_path" { type = string }

variable "storage_account_name" { type = string }
variable "state_table_name" {
  type    = string
  default = "failoverstate"
}

variable "cooldown_minutes" {
  type    = number
  default = 5
}

variable "region_a" { type = string }
variable "region_b" { type = string }

variable "dns_zone_name" { type = string }     # ex: "example.com"
variable "dns_record_name" { type = string }   # ex: "app"

variable "azure_tenant_id" { type = string }
variable "azure_client_id" { type = string }
variable "azure_client_secret" {
  type      = string
  sensitive = true
}

variable "logicapp_interval_minutes" {
  type    = number
  default = 5
}
