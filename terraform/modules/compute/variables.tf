variable "project" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "aws_account_id" { type = string }

variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "alb_sg_id" { type = string }
variable "api_sg_id" { type = string }

variable "ecr_repository_url" { type = string }

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS ALB listener"
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "api_min_count" {
  type    = number
  default = 1
}

variable "api_max_count" {
  type    = number
  default = 4
}

variable "env_vars" {
  type        = map(string)
  default     = {}
  description = "Environment variables to pass to the API container"
}
