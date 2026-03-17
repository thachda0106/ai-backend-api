variable "project" { type = string }
variable "environment" { type = string }
variable "ecs_cluster_name" { type = string }
variable "api_service_name" { type = string }
variable "alb_arn_suffix" { type = string }
variable "tg_arn_suffix" { type = string }

variable "alarm_email" {
  type        = string
  default     = ""
  description = "Email address to notify on alarm state changes (optional)"
}

variable "cpu_threshold" {
  type    = number
  default = 80
}

variable "memory_threshold" {
  type    = number
  default = 80
}

variable "error_5xx_threshold" {
  type        = number
  default     = 5
  description = "5xx error count per minute that triggers the alarm"
}
