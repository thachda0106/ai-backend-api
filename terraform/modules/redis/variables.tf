variable "project" { type = string }
variable "environment" { type = string }

variable "node_type" {
  type        = string
  default     = "cache.t3.micro"
  description = "ElastiCache node instance type"
}

variable "engine_version" {
  type        = string
  default     = "7.1"
  description = "Redis engine version"
}

variable "num_cache_clusters" {
  type        = number
  default     = 1
  description = "Number of nodes (1 = single-node dev; 2 = primary+replica for staging/prod)"
}

variable "automatic_failover" {
  type        = bool
  default     = false
  description = "Enable automatic failover (requires num_cache_clusters >= 2)"
}

variable "multi_az" {
  type        = bool
  default     = false
  description = "Enable Multi-AZ for the replication group"
}

variable "snapshot_retention" {
  type        = number
  default     = 1
  description = "Days to retain automatic snapshots (0 = disabled)"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the ElastiCache subnet group"
}

variable "redis_sg_id" {
  type        = string
  description = "Security group ID for Redis (from network module)"
}

variable "auth_token" {
  type        = string
  sensitive   = true
  default     = ""
  description = "Redis AUTH token (password). Required when transit_encryption_enabled=true"
}
