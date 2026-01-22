variable "subscription_id" {
  type        = string
  description = "Azure subscription id used by Terraform."
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "storage_account_name" {
  type        = string
  description = "Globally unique, lowercase, 3-24 chars."
}

variable "function_app_name" {
  type = string
}

variable "primary_endpoint" {
  type = string
}

variable "secondary_endpoint" {
  type = string
}

variable "cooldown_minutes" {
  type    = number
  default = 10
}

variable "logicapp_interval_minutes" {
  type    = number
  default = 1
}

variable "functions_zip_path" {
  type        = string
  description = "Path to functions.zip created from ./functions folder (e.g. ../functions.zip)"
}

variable "health_function_key" {
  type        = string
  sensitive   = true
  description = "Function key for health_check"
}

variable "failover_function_key" {
  type        = string
  sensitive   = true
  description = "Function key for do_failover"
}
