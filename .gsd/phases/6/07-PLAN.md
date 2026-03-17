---
phase: 6
plan: 7
wave: 4
depends_on: [6.1, 6.2, 6.3, 6.4, 6.5, 6.6]
files_modified:
  - terraform/bootstrap/main.tf
  - terraform/versions.tf
  - terraform/environments/dev/main.tf
  - terraform/environments/dev/variables.tf
  - terraform/environments/dev/terraform.tfvars
  - terraform/environments/staging/main.tf
  - terraform/environments/staging/variables.tf
  - terraform/environments/staging/terraform.tfvars
  - terraform/environments/production/main.tf
  - terraform/environments/production/variables.tf
  - terraform/environments/production/terraform.tfvars
autonomous: true

must_haves:
  truths:
    - "terraform/versions.tf pins Terraform >= 1.7 and AWS provider ~> 5.0"
    - "terraform/bootstrap/main.tf creates S3 bucket with versioning and native locking"
    - "All 3 environment root configs call all required modules"
    - "terraform validate passes in environments/dev"
---

# Plan 6.7: Environment Root Configs + Remote State Bootstrap

## Objective
Create the environment root configurations (dev, staging, production) that compose all modules together, plus the bootstrap script to create the S3 remote state bucket. This wires all modules into deployable stacks per environment.

## Context
- @.gsd/phases/6/RESEARCH.md — native S3 locking decision, no DynamoDB
- @terraform/modules/*/outputs.tf — all module outputs wired here

## Tasks

<task type="auto">
  <name>Create shared versions.tf and bootstrap script</name>
  <files>
    terraform/versions.tf
    terraform/bootstrap/main.tf
  </files>
  <action>
    Create `terraform/versions.tf` (shared Terraform and provider version pins):
    ```hcl
    terraform {
      required_version = ">= 1.7.0"

      required_providers {
        aws = {
          source  = "hashicorp/aws"
          version = "~> 5.0"
        }
      }
    }
    ```

    Create `terraform/bootstrap/main.tf` (run once to create remote state bucket):
    ```hcl
    # Bootstrap: run this ONCE per AWS account to create the S3 remote state bucket.
    # After running: add the bucket name to each environment's backend {} block.
    #
    # Usage:
    #   terraform init
    #   terraform apply -var="aws_region=us-east-1" -var="project=ai-backend-api"

    terraform {
      required_version = ">= 1.7.0"
      required_providers {
        aws = { source = "hashicorp/aws"; version = "~> 5.0" }
      }
    }

    variable "aws_region" { type = string; default = "us-east-1" }
    variable "project"    { type = string }

    provider "aws" { region = var.aws_region }

    data "aws_caller_identity" "current" {}

    locals {
      bucket_name = "${var.project}-tfstate-${data.aws_caller_identity.current.account_id}"
    }

    resource "aws_s3_bucket" "tfstate" {
      bucket        = local.bucket_name
      force_destroy = false  # Safety: prevent accidental destruction

      tags = { Purpose = "Terraform remote state" }
    }

    resource "aws_s3_bucket_versioning" "tfstate" {
      bucket = aws_s3_bucket.tfstate.id
      versioning_configuration { status = "Enabled" }
    }

    resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
      bucket = aws_s3_bucket.tfstate.id
      rule {
        apply_server_side_encryption_by_default {
          sse_algorithm = "AES256"
        }
      }
    }

    resource "aws_s3_bucket_public_access_block" "tfstate" {
      bucket                  = aws_s3_bucket.tfstate.id
      block_public_acls       = true
      block_public_policy     = true
      ignore_public_acls      = true
      restrict_public_buckets = true
    }

    output "state_bucket_name" { value = local.bucket_name }
    output "state_bucket_arn"  { value = aws_s3_bucket.tfstate.arn }
    ```
  </action>
  <verify>cd terraform/bootstrap && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0 in bootstrap/; versions.tf exists at terraform root</done>
</task>

<task type="auto">
  <name>Create all 3 environment root configurations</name>
  <files>
    terraform/environments/dev/main.tf
    terraform/environments/dev/variables.tf
    terraform/environments/dev/terraform.tfvars
    terraform/environments/staging/main.tf
    terraform/environments/staging/variables.tf
    terraform/environments/staging/terraform.tfvars
    terraform/environments/production/main.tf
    terraform/environments/production/variables.tf
    terraform/environments/production/terraform.tfvars
  </files>
  <action>
    For each environment (dev / staging / production), create 3 files with the same structure but different variable values.

    **`variables.tf`** (identical across all envs):
    ```hcl
    variable "project"         { type = string }
    variable "environment"     { type = string }
    variable "aws_region"      { type = string }
    variable "aws_account_id"  { type = string }
    variable "azs"             { type = list(string) }
    variable "certificate_arn" { type = string }

    # Redis
    variable "redis_node_type"        { type = string }
    variable "redis_num_clusters"     { type = number }
    variable "redis_automatic_failover" { type = bool }
    variable "redis_multi_az"         { type = bool }

    # Compute
    variable "api_cpu"          { type = number }
    variable "api_memory"       { type = number }
    variable "api_desired_count"{ type = number }
    variable "api_min_count"    { type = number }
    variable "api_max_count"    { type = number }
    variable "image_tag"        { type = string; default = "latest" }

    # Qdrant
    variable "qdrant_desired_count" { type = number }
    variable "qdrant_cpu"           { type = number }
    variable "qdrant_memory"        { type = number }

    # Observability
    variable "alarm_email" { type = string; default = "" }
    ```

    **`main.tf`** for each environment — identical structure, module paths are relative (`../../modules/...`):
    ```hcl
    terraform {
      required_version = ">= 1.7.0"
      required_providers {
        aws = { source = "hashicorp/aws"; version = "~> 5.0" }
      }
      backend "s3" {
        # Populated after bootstrap — fill in bucket name
        bucket       = "REPLACE_WITH_BOOTSTRAP_OUTPUT"
        key          = "ENV_NAME/terraform.tfstate"
        region       = "us-east-1"
        encrypt      = true
        use_lockfile = true  # Native S3 locking (no DynamoDB needed)
      }
    }

    provider "aws" { region = var.aws_region }

    module "network" {
      source      = "../../modules/network"
      project     = var.project
      environment = var.environment
      azs         = var.azs
    }

    module "registry" {
      source      = "../../modules/registry"
      project     = var.project
      environment = var.environment
    }

    module "redis" {
      source           = "../../modules/redis"
      project          = var.project
      environment      = var.environment
      subnet_ids       = module.network.private_subnet_ids
      redis_sg_id      = module.network.redis_sg_id
      node_type        = var.redis_node_type
      num_cache_clusters     = var.redis_num_clusters
      automatic_failover     = var.redis_automatic_failover
      multi_az               = var.redis_multi_az
    }

    module "compute" {
      source              = "../../modules/compute"
      project             = var.project
      environment         = var.environment
      aws_region          = var.aws_region
      aws_account_id      = var.aws_account_id
      vpc_id              = module.network.vpc_id
      public_subnet_ids   = module.network.public_subnet_ids
      private_subnet_ids  = module.network.private_subnet_ids
      alb_sg_id           = module.network.alb_sg_id
      api_sg_id           = module.network.api_sg_id
      ecr_repository_url  = module.registry.repository_url
      image_tag           = var.image_tag
      certificate_arn     = var.certificate_arn
      api_cpu             = var.api_cpu
      api_memory          = var.api_memory
      api_desired_count   = var.api_desired_count
      api_min_count       = var.api_min_count
      api_max_count       = var.api_max_count
    }

    module "qdrant" {
      source              = "../../modules/qdrant"
      project             = var.project
      environment         = var.environment
      aws_region          = var.aws_region
      private_subnet_ids  = module.network.private_subnet_ids
      qdrant_sg_id        = module.network.qdrant_sg_id
      efs_sg_id           = module.network.efs_sg_id
      ecs_cluster_id      = module.compute.ecs_cluster_id
      execution_role_arn  = module.compute.execution_role_arn
      desired_count       = var.qdrant_desired_count
      cpu                 = var.qdrant_cpu
      memory              = var.qdrant_memory
    }

    module "observability" {
      source            = "../../modules/observability"
      project           = var.project
      environment       = var.environment
      ecs_cluster_name  = module.compute.ecs_cluster_name
      api_service_name  = module.compute.api_service_name
      alb_arn_suffix    = module.compute.alb_arn_suffix
      tg_arn_suffix     = module.compute.tg_arn_suffix
      alarm_email       = var.alarm_email
    }
    ```

    Note: Add `alb_arn_suffix` and `tg_arn_suffix` outputs to `terraform/modules/compute/outputs.tf` (missed in Plan 6.5):
    ```hcl
    output "alb_arn_suffix" { value = aws_lb.api.arn_suffix }
    output "tg_arn_suffix"  { value = aws_lb_target_group.api.arn_suffix }
    ```

    **`terraform.tfvars`** per environment (environment-specific sizes):

    *dev:*
    ```hcl
    project         = "ai-backend-api"
    environment     = "dev"
    aws_region      = "us-east-1"
    azs             = ["us-east-1a", "us-east-1b"]
    certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/REPLACE_ME"

    redis_node_type          = "cache.t3.micro"
    redis_num_clusters       = 1
    redis_automatic_failover = false
    redis_multi_az           = false

    api_cpu           = 256
    api_memory        = 512
    api_desired_count = 1
    api_min_count     = 1
    api_max_count     = 2

    qdrant_desired_count = 1
    qdrant_cpu           = 512
    qdrant_memory        = 1024
    ```

    *staging:*
    ```hcl
    # Same variables, moderate sizes
    redis_node_type          = "cache.t3.small"
    redis_num_clusters       = 2
    redis_automatic_failover = true
    redis_multi_az           = false
    api_cpu = 512; api_memory = 1024; api_desired_count = 1
    qdrant_cpu = 1024; qdrant_memory = 2048
    ```

    *production:*
    ```hcl
    # Same variables, production sizes
    redis_node_type          = "cache.r7g.large"
    redis_num_clusters       = 2
    redis_automatic_failover = true
    redis_multi_az           = true
    api_cpu = 1024; api_memory = 2048; api_desired_count = 2; api_max_count = 8
    qdrant_cpu = 2048; qdrant_memory = 4096
    ```
  </action>
  <verify>cd terraform/environments/dev && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0 for dev environment; all modules wired with correct variable names</done>
</task>

## Success Criteria
- [ ] `terraform validate` passes in `terraform/bootstrap/`
- [ ] `terraform validate` passes in `terraform/environments/dev/`
- [ ] S3 bucket uses `use_lockfile = true` (no DynamoDB table)
- [ ] All 3 environments have distinct `terraform.tfvars` with appropriate sizing
- [ ] `aws_account_id` is a variable (not hardcoded) — passed via tfvars or TF_VAR env
