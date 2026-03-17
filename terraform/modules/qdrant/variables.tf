variable "project" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for ECS service and EFS mount targets"
}

variable "qdrant_sg_id" {
  type        = string
  description = "Security group ID for Qdrant ECS tasks"
}

variable "efs_sg_id" {
  type        = string
  description = "Security group ID for EFS mount targets"
}

variable "ecs_cluster_id" {
  type        = string
  description = "ECS cluster ID (from compute module)"
}

variable "execution_role_arn" {
  type        = string
  description = "ECS task execution role ARN (from compute module)"
}

variable "qdrant_image" {
  type        = string
  default     = "qdrant/qdrant:v1.14.0"
  description = "Qdrant Docker image (pinned version)"
}

variable "cpu" {
  type        = number
  default     = 1024
  description = "Task CPU units (1024 = 1 vCPU)"
}

variable "memory" {
  type        = number
  default     = 2048
  description = "Task memory in MiB"
}

variable "desired_count" {
  type        = number
  default     = 1
  description = "Number of Qdrant tasks to run"
}

variable "qdrant_api_key" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Optional Qdrant API key for authentication"
}
