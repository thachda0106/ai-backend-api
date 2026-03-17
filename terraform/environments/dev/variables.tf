variable "project" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "aws_account_id" { type = string }
variable "azs" { type = list(string) }
variable "certificate_arn" { type = string }

variable "redis_node_type" { type = string }
variable "redis_num_clusters" { type = number }
variable "redis_automatic_failover" { type = bool }
variable "redis_multi_az" { type = bool }

variable "api_cpu" { type = number }
variable "api_memory" { type = number }
variable "api_desired_count" { type = number }
variable "api_min_count" { type = number }
variable "api_max_count" { type = number }

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "qdrant_desired_count" { type = number }
variable "qdrant_cpu" { type = number }
variable "qdrant_memory" { type = number }

variable "alarm_email" {
  type    = string
  default = ""
}
