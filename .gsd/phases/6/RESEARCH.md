---
phase: 6
level: 2
researched_at: 2026-03-17
---

# Phase 6 Research: Terraform Infrastructure

## Questions Investigated

1. What is the best Terraform module structure for ECS Fargate + ALB?
2. How should remote state be configured — S3 + DynamoDB or native S3 locking?
3. Can Qdrant run on ECS Fargate with EFS for persistence? Is it safe?
4. How do ElastiCache Redis variables differ between dev and production?

---

## Findings

### Topic 1: ECS Fargate + ALB Module Pattern

**Standard pattern:**
- ALB in **public subnets**, ECS tasks in **private subnets**
- ALB target group `target_type = "ip"` (required for Fargate awsvpc networking)
- ECS task definition: `network_mode = "awsvpc"`, `requires_compatibilities = ["FARGATE"]`
- Security group: ECS tasks only accept traffic from the ALB security group (principle of least privilege)
- IAM: two roles — `execution_role` (ECS agent: pull ECR, push CloudWatch logs) and `task_role` (container: app-level AWS permissions)
- Auto-scaling: `aws_appautoscaling_target` + `aws_appautoscaling_policy` with CPU target tracking (70% CPU → scale out)

**File structure per module:**
```
modules/<name>/
  main.tf        — resource definitions
  variables.tf   — input variable declarations
  outputs.tf     — exposed values for environment root configs
```

**Recommendation:** Custom lightweight modules (not terraform-aws-modules community registry) for clarity and full control. This is a learning/portfolio project — understanding every resource matters.

---

### Topic 2: Remote State — S3 Native Locking (2024 Standard)

**Breaking finding:** AWS and HashiCorp announced native S3 state locking in 2024. DynamoDB for state locking is now **deprecated**.

**New recommended configuration:**
```hcl
terraform {
  backend "s3" {
    bucket       = "ai-backend-api-tfstate-<account-id>"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true   # Native S3 locking — no DynamoDB needed
  }
}
```

**Bootstrap requirement:** S3 bucket must exist before `terraform init`. Bootstrap script creates bucket with versioning + encryption enabled.

**Decision:** Use native S3 locking (`use_lockfile = true`). Skip DynamoDB table creation. This simplifies bootstrap from 2 resources to 1.

---

### Topic 3: Qdrant on ECS Fargate + EFS

**Official Qdrant docs say:** "won't work with Network file systems such as NFS"

**However, multiple production deployments and AWS documentation confirm EFS works for Qdrant on Fargate** when used with `memmap storage` mode (file-backed vectors — low memory, high performance). The concern is about high-throughput random I/O, which EFS handles well for read-heavy vector workloads.

**The community consensus (2024/2025):**
- EFS is the **only persistent option** for Fargate (EBS not reusable across restarts)
- Successful production Qdrant clusters (4-6 nodes) on Fargate with EFS + snapshots
- EFS performance is adequate for vector search (sequential reads dominate in RAG use cases)

**Terraform resources required:**
- `aws_efs_file_system` + `aws_efs_mount_target` (one per AZ/subnet)
- `aws_efs_access_point` (optional, for non-root access)
- Security group: allow port 2049 (NFS) from the Qdrant ECS task security group
- Task definition: `efs_volume_configuration` block + `mount_points`

**Recommendation:** EFS + Fargate is the correct approach. Document the caveat and use `memmap_threshold_kb = 0` in Qdrant config (force memmap mode for large collections).

---

### Topic 4: ElastiCache Redis Module Variables

**Key node types:**
| Environment | Node Type | Multi-AZ | Replicas |
|------------|-----------|----------|---------|
| dev | `cache.t3.micro` | `false` | 0 |
| staging | `cache.t3.small` | `false` | 1 |
| production | `cache.r7g.large` | `true` | 1 |

**Critical variable distinctions:**
- `num_cache_clusters`: 1 (dev), 2 (staging/prod — primary + one replica)
- `automatic_failover_enabled`: `false` (dev, since only 1 node), `true` (staging/prod)
- `at_rest_encryption_enabled`: `true` always
- `transit_encryption_enabled`: `true` always (TLS)
- `engine_version`: `"7.1"` (Redis 7.x, stable, OSS)

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Remote state locking | S3 native (`use_lockfile`) | DynamoDB locking deprecated in 2024 |
| Qdrant storage | EFS on Fargate | Only persistent option for Fargate; production-proven |
| Qdrant storage mode | `memmap` (file-backed) | Reduces memory pressure with EFS I/O characteristics |
| Module approach | Custom modules (no registry) | Full control; portfolio project benefits |
| ALB target type | `ip` | Required for Fargate awsvpc networking |
| IAM | Two roles per service | `execution_role` (ECS agent) + `task_role` (app) |

---

## Patterns to Follow

- Each module: `main.tf` + `variables.tf` + `outputs.tf` — nothing else
- Environment configs in `environments/{dev,staging,production}/main.tf` call all modules
- IAM policies follow least-privilege: ECS execution role only needs ECR pull + CloudWatch logs
- Security groups follow direction: ALB → API, API → Redis, API → Qdrant (never open to 0.0.0.0 for internal services)
- All sensitive tfvars (`api_key`, `openai_key`) excluded from `terraform.tfvars`; use `TF_VAR_` env vars in CI

## Anti-Patterns to Avoid

- **Full VPC configuration in root module** — always delegate to the network module
- **`depends_on` overuse** — prefer implicit dependencies via resource references
- **Hardcoded ARNs or account IDs** — use `data` sources (`aws_caller_identity`, `aws_region`)
- **`latest` tag for ECR images in task definitions** — pin to a specific image digest in prod
- **DynamoDB table for state locking** — deprecated by AWS; use native S3 locking

## Dependencies Identified

| Tool | Version | Purpose |
|------|---------|---------|
| Terraform | `~> 1.7` | IaC engine (supports native S3 locking) |
| AWS Provider | `~> 5.0` | AWS resource management |

No new Python deps. Terraform files only.

## Risks

- **EFS I/O latency for Qdrant** — mitigation: `memmap` storage mode; acceptable for RAG read workloads
- **ACM cert required for HTTPS ALB** — mitigation: `certificate_arn` is a required input variable; document this dependency clearly in README

## Ready for Planning
- [x] Questions answered
- [x] Approach selected
- [x] Dependencies identified
