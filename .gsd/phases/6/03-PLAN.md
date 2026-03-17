---
phase: 6
plan: 3
wave: 2
depends_on: [6.1]
files_modified:
  - terraform/modules/redis/main.tf
  - terraform/modules/redis/variables.tf
  - terraform/modules/redis/outputs.tf
autonomous: true

must_haves:
  truths:
    - "ElastiCache replication group created"
    - "Variables allow single-node (dev) and multi-AZ (prod) configuration"
    - "Security group from network module applied"
    - "At-rest and in-transit encryption enabled"
---

# Plan 6.3: Redis Module (ElastiCache)

## Objective
Create `terraform/modules/redis` — an ElastiCache Redis replication group configurable for single-node (dev) or multi-AZ with replica (staging/prod). The module accepts VPC and security group IDs from the network module outputs.

## Context
- @.gsd/phases/6/RESEARCH.md — ElastiCache sizing table
- @terraform/modules/network/outputs.tf — subnet and SG IDs this module consumes (created in Plan 6.1)

## Tasks

<task type="auto">
  <name>Create ElastiCache Redis module</name>
  <files>
    terraform/modules/redis/main.tf
    terraform/modules/redis/variables.tf
    terraform/modules/redis/outputs.tf
  </files>
  <action>
    Create `terraform/modules/redis/variables.tf`:
    ```hcl
    variable "project"     { type = string }
    variable "environment" { type = string }

    variable "node_type"              { type = string; default = "cache.t3.micro" }
    variable "engine_version"         { type = string; default = "7.1" }
    variable "num_cache_clusters"     { type = number; default = 1 }
    variable "automatic_failover"     { type = bool;   default = false }
    variable "multi_az"               { type = bool;   default = false }
    variable "snapshot_retention"     { type = number; default = 1 }

    variable "subnet_ids"             { type = list(string) }  # private subnets from network module
    variable "redis_sg_id"            { type = string }        # redis_sg from network module
    variable "auth_token"             { type = string; sensitive = true; default = "" }
    ```

    Create `terraform/modules/redis/main.tf`:

    **Subnet Group:**
    ```hcl
    resource "aws_elasticache_subnet_group" "redis" {
      name       = "${var.project}-${var.environment}-redis"
      subnet_ids = var.subnet_ids
    }
    ```

    **Replication Group:**
    ```hcl
    resource "aws_elasticache_replication_group" "redis" {
      replication_group_id = "${var.project}-${var.environment}-redis"
      description          = "Redis for ${var.project} ${var.environment}"

      engine               = "redis"
      engine_version       = var.engine_version
      node_type            = var.node_type
      num_cache_clusters   = var.num_cache_clusters
      port                 = 6379

      subnet_group_name          = aws_elasticache_subnet_group.redis.name
      security_group_ids         = [var.redis_sg_id]

      automatic_failover_enabled = var.automatic_failover
      multi_az_enabled           = var.multi_az

      at_rest_encryption_enabled = true
      transit_encryption_enabled = true
      auth_token                 = var.auth_token != "" ? var.auth_token : null

      snapshot_retention_limit = var.snapshot_retention
      snapshot_window          = "03:00-05:00"
      maintenance_window       = "sun:05:00-sun:07:00"

      tags = {
        Project     = var.project
        Environment = var.environment
      }
    }
    ```

    Create `terraform/modules/redis/outputs.tf`:
    ```hcl
    output "primary_endpoint"    { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
    output "reader_endpoint"     { value = aws_elasticache_replication_group.redis.reader_endpoint_address }
    output "port"                { value = 6379 }
    output "replication_group_id" { value = aws_elasticache_replication_group.redis.id }
    ```
  </action>
  <verify>cd terraform/modules/redis && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0; ElastiCache replication group + subnet group defined with encryption and configurable multi-AZ</done>
</task>

## Success Criteria
- [ ] `terraform validate` passes in `terraform/modules/redis/`
- [ ] `num_cache_clusters` + `automatic_failover` variables allow single-node and multi-AZ configs
- [ ] Both `at_rest_encryption_enabled` and `transit_encryption_enabled` set to `true`
- [ ] `outputs.tf` exports `primary_endpoint`, `reader_endpoint`, `port`
