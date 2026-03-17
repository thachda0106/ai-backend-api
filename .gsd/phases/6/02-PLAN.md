---
phase: 6
plan: 2
wave: 1
depends_on: []
files_modified:
  - terraform/modules/registry/main.tf
  - terraform/modules/registry/variables.tf
  - terraform/modules/registry/outputs.tf
autonomous: true

must_haves:
  truths:
    - "ECR repository created for the API image"
    - "Lifecycle policy keeps last 10 images"
    - "Image scan on push enabled"
    - "outputs.tf exposes repository_url and repository_arn"
---

# Plan 6.2: Registry Module (ECR)

## Objective
Create the `terraform/modules/registry` module that provisions the ECR repository where Docker images are pushed during CI/CD and pulled by ECS task definitions.

## Context
- @.gsd/phases/6/RESEARCH.md — module structure pattern
- @Dockerfile — the image that will be pushed to this registry

## Tasks

<task type="auto">
  <name>Create ECR registry module</name>
  <files>
    terraform/modules/registry/main.tf
    terraform/modules/registry/variables.tf
    terraform/modules/registry/outputs.tf
  </files>
  <action>
    Create `terraform/modules/registry/variables.tf`:
    ```hcl
    variable "project"     { type = string }
    variable "environment" { type = string }
    variable "image_tag_mutability" {
      type    = string
      default = "MUTABLE"
      # Use IMMUTABLE in production to prevent tag overwriting
    }
    variable "scan_on_push" { type = bool; default = true }
    variable "lifecycle_policy_count" {
      type    = number
      default = 10
      description = "Number of tagged images to keep"
    }
    ```

    Create `terraform/modules/registry/main.tf`:

    **ECR Repository:**
    ```hcl
    resource "aws_ecr_repository" "api" {
      name                 = "${var.project}-${var.environment}-api"
      image_tag_mutability = var.image_tag_mutability

      image_scanning_configuration {
        scan_on_push = var.scan_on_push
      }

      tags = {
        Project     = var.project
        Environment = var.environment
      }
    }
    ```

    **Lifecycle Policy** (keep last N tagged images, expire untagged after 1 day):
    ```hcl
    resource "aws_ecr_lifecycle_policy" "api" {
      repository = aws_ecr_repository.api.name

      policy = jsonencode({
        rules = [
          {
            rulePriority = 1
            description  = "Expire untagged images after 1 day"
            selection = {
              tagStatus   = "untagged"
              countType   = "sinceImagePushed"
              countUnit   = "days"
              countNumber = 1
            }
            action = { type = "expire" }
          },
          {
            rulePriority = 2
            description  = "Keep last ${var.lifecycle_policy_count} tagged images"
            selection = {
              tagStatus     = "tagged"
              tagPrefixList = ["v"]
              countType     = "imageCountMoreThan"
              countNumber   = var.lifecycle_policy_count
            }
            action = { type = "expire" }
          }
        ]
      })
    }
    ```

    Create `terraform/modules/registry/outputs.tf`:
    ```hcl
    output "repository_url"  { value = aws_ecr_repository.api.repository_url }
    output "repository_arn"  { value = aws_ecr_repository.api.arn }
    output "repository_name" { value = aws_ecr_repository.api.name }
    ```
  </action>
  <verify>cd terraform/modules/registry && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0; ECR repo + lifecycle policy defined; outputs.tf exports repository_url, repository_arn, repository_name</done>
</task>

## Success Criteria
- [ ] `terraform validate` passes in `terraform/modules/registry/`
- [ ] ECR repository with scan-on-push enabled
- [ ] Lifecycle policy: expire untagged after 1 day, keep last 10 tagged
- [ ] `outputs.tf` exports `repository_url`, `repository_arn`, `repository_name`
