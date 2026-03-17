---
phase: 6
plan: 1
wave: 1
depends_on: []
files_modified:
  - terraform/modules/network/main.tf
  - terraform/modules/network/variables.tf
  - terraform/modules/network/outputs.tf
autonomous: true

must_haves:
  truths:
    - "VPC with CIDR var.vpc_cidr created"
    - "2 public and 2 private subnets across 2 AZs"
    - "Internet Gateway + NAT Gateway + route tables created"
    - "Security groups created for ALB, API, Redis, Qdrant, EFS"
---

# Plan 6.1: Network Module

## Objective
Create the `terraform/modules/network` module that provisions the complete VPC topology: public/private subnets, routing, and all security groups. Every other module consumes outputs from this one (subnet IDs, VPC ID, security group IDs), so it's the foundation dependency.

## Context
- @.gsd/phases/6/RESEARCH.md — networking patterns
- @.gsd/SPEC.md — AWS target, multi-environment

## Tasks

<task type="auto">
  <name>Create network module — VPC, subnets, routing</name>
  <files>
    terraform/modules/network/main.tf
    terraform/modules/network/variables.tf
    terraform/modules/network/outputs.tf
  </files>
  <action>
    Create `terraform/modules/network/variables.tf`:
    ```hcl
    variable "project"     { type = string }
    variable "environment" { type = string }
    variable "vpc_cidr"    { type = string; default = "10.0.0.0/16" }
    variable "public_subnet_cidrs"  { type = list(string); default = ["10.0.1.0/24", "10.0.2.0/24"] }
    variable "private_subnet_cidrs" { type = list(string); default = ["10.0.10.0/24", "10.0.11.0/24"] }
    variable "azs" { type = list(string) }  # e.g. ["us-east-1a", "us-east-1b"]
    ```

    Create `terraform/modules/network/main.tf` with:

    **VPC:**
    - `aws_vpc` with `cidr_block = var.vpc_cidr`, `enable_dns_hostnames = true`, `enable_dns_support = true`
    - Tag: `Name = "${var.project}-${var.environment}-vpc"`

    **Subnets** (use `count = 2`):
    - `aws_subnet` public — `cidr = var.public_subnet_cidrs[count.index]`, `map_public_ip_on_launch = true`, AZ from `var.azs[count.index]`
    - `aws_subnet` private — `cidr = var.private_subnet_cidrs[count.index]`, `map_public_ip_on_launch = false`

    **Internet Gateway:** `aws_internet_gateway` attached to VPC

    **NAT Gateway:** 1 instance (cost-optimised — single AZ for dev). Requires `aws_eip` (domain = "vpc").

    **Route Tables:**
    - Public route table: `0.0.0.0/0 → igw`; associated with both public subnets
    - Private route table: `0.0.0.0/0 → nat`; associated with both private subnets

    **Security Groups** (5 total, all in the VPC):

    1. `alb_sg` — ingress 80+443 from `0.0.0.0/0`; egress all
    2. `api_sg` — ingress 8000 from `alb_sg` only; egress all
    3. `redis_sg` — ingress 6379 from `api_sg` only; egress all
    4. `qdrant_sg` — ingress 6333+6334 from `api_sg` only; egress all
    5. `efs_sg` — ingress 2049 (NFS) from `api_sg` + `qdrant_sg`; egress all

    Create `terraform/modules/network/outputs.tf` exposing:
    - `vpc_id`, `public_subnet_ids` (list), `private_subnet_ids` (list)
    - `alb_sg_id`, `api_sg_id`, `redis_sg_id`, `qdrant_sg_id`, `efs_sg_id`
  </action>
  <verify>cd terraform/modules/network && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0; all 5 security groups and VPC resources defined; outputs.tf exports all required values</done>
</task>

## Success Criteria
- [ ] `terraform validate` passes in `terraform/modules/network/`
- [ ] VPC, 4 subnets (2 public, 2 private), IGW, NAT GW, 2 route tables defined
- [ ] 5 security groups: alb, api, redis, qdrant, efs
- [ ] `outputs.tf` exports all IDs needed by downstream modules
