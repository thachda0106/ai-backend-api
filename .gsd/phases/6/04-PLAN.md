---
phase: 6
plan: 4
wave: 2
depends_on: [6.1]
files_modified:
  - terraform/modules/qdrant/main.tf
  - terraform/modules/qdrant/variables.tf
  - terraform/modules/qdrant/outputs.tf
autonomous: true

must_haves:
  truths:
    - "EFS file system + mount targets created for Qdrant storage"
    - "ECS task definition mounts EFS at /qdrant/storage"
    - "ECS Fargate service with desired_count variable"
    - "QDRANT__STORAGE__MEMMAP_THRESHOLD_KB=0 set (force memmap mode)"
---

# Plan 6.4: Qdrant Module (ECS Fargate + EFS)

## Objective
Create `terraform/modules/qdrant` — ECS Fargate service running Qdrant with EFS persistent storage. EFS is mounted at `/qdrant/storage`. Memmap storage mode is forced via environment variable to make EFS I/O characteristics acceptable for production use.

## Context
- @.gsd/phases/6/RESEARCH.md — Qdrant+EFS decision and memmap rationale
- @terraform/modules/network/outputs.tf — subnet IDs, qdrant_sg_id, efs_sg_id consumed here

## Tasks

<task type="auto">
  <name>Create EFS filesystem and Qdrant ECS Fargate service</name>
  <files>
    terraform/modules/qdrant/main.tf
    terraform/modules/qdrant/variables.tf
    terraform/modules/qdrant/outputs.tf
  </files>
  <action>
    Create `terraform/modules/qdrant/variables.tf`:
    ```hcl
    variable "project"          { type = string }
    variable "environment"      { type = string }
    variable "aws_region"       { type = string }

    variable "private_subnet_ids" { type = list(string) }
    variable "qdrant_sg_id"       { type = string }
    variable "efs_sg_id"          { type = string }

    variable "ecs_cluster_id"     { type = string }      # from compute module
    variable "execution_role_arn" { type = string }

    variable "qdrant_image"       { type = string; default = "qdrant/qdrant:v1.14.0" }
    variable "cpu"                { type = number; default = 1024 }
    variable "memory"             { type = number; default = 2048 }
    variable "desired_count"      { type = number; default = 1 }
    variable "qdrant_api_key"     { type = string; sensitive = true; default = "" }
    ```

    Create `terraform/modules/qdrant/main.tf` with these resources in order:

    **EFS File System:**
    ```hcl
    resource "aws_efs_file_system" "qdrant" {
      creation_token   = "${var.project}-${var.environment}-qdrant"
      encrypted        = true
      performance_mode = "generalPurpose"
      throughput_mode  = "bursting"

      tags = { Name = "${var.project}-${var.environment}-qdrant-efs" }
    }
    ```

    **EFS Mount Targets** (one per private subnet, count = length(var.private_subnet_ids)):
    ```hcl
    resource "aws_efs_mount_target" "qdrant" {
      count           = length(var.private_subnet_ids)
      file_system_id  = aws_efs_file_system.qdrant.id
      subnet_id       = var.private_subnet_ids[count.index]
      security_groups = [var.efs_sg_id]
    }
    ```

    **CloudWatch Log Group:**
    ```hcl
    resource "aws_cloudwatch_log_group" "qdrant" {
      name              = "/ecs/${var.project}-${var.environment}/qdrant"
      retention_in_days = 30
    }
    ```

    **ECS Task Definition** (Fargate, awsvpc):
    - cpu = var.cpu, memory = var.memory
    - volume block with `efs_volume_configuration`: file_system_id, transit_encryption = "ENABLED"
    - container definition JSON with:
      - image = var.qdrant_image
      - portMappings: 6333 (REST), 6334 (gRPC)
      - mountPoints: containerPath = "/qdrant/storage", sourceVolume = "qdrant-storage"
      - environment vars:
        - `QDRANT__STORAGE__STORAGE_PATH = "/qdrant/storage"`
        - `QDRANT__STORAGE__SNAPSHOTS_PATH = "/qdrant/storage/snapshots"`
        - `QDRANT__SERVICE__GRPC_PORT = "6334"`
        - `QDRANT__LOG_LEVEL = "INFO"`
        - Conditionally: `QDRANT__SERVICE__API_KEY` if var.qdrant_api_key != ""
      - logConfiguration: awslogs driver → log group above

    **ECS Service** (Fargate):
    - cluster = var.ecs_cluster_id
    - desired_count = var.desired_count
    - network_configuration: subnets = private, security_groups = [qdrant_sg_id]
    - platform_version = "1.4.0" (required for EFS support)
    - Add `depends_on` on all aws_efs_mount_target resources to ensure EFS is ready

    Create `terraform/modules/qdrant/outputs.tf`:
    ```hcl
    output "efs_id"           { value = aws_efs_file_system.qdrant.id }
    output "service_name"     { value = aws_ecs_service.qdrant.name }
    output "rest_port"        { value = 6333 }
    output "grpc_port"        { value = 6334 }
    ```
  </action>
  <verify>cd terraform/modules/qdrant && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0; EFS + mount targets + ECS task def (with efs_volume_configuration) + ECS service all defined</done>
</task>

## Success Criteria
- [ ] `terraform validate` passes in `terraform/modules/qdrant/`
- [ ] EFS file system with encrypted=true
- [ ] EFS mount targets use count over private_subnet_ids
- [ ] ECS task definition has `efs_volume_configuration` and mounts at `/qdrant/storage`
- [ ] `platform_version = "1.4.0"` on ECS service (EFS requirement)
