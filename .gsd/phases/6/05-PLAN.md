---
phase: 6
plan: 5
wave: 3
depends_on: [6.1, 6.2]
files_modified:
  - terraform/modules/compute/main.tf
  - terraform/modules/compute/variables.tf
  - terraform/modules/compute/outputs.tf
autonomous: true

must_haves:
  truths:
    - "ECS cluster created"
    - "ALB with HTTP→HTTPS redirect and HTTPS listener created"
    - "ECS Fargate task definition for API with awsvpc network mode"
    - "ECS auto-scaling configured with CPU target tracking at 70%"
    - "IAM execution role and task role defined"
---

# Plan 6.5: Compute Module (ECS Fargate + ALB + Auto-scaling)

## Objective
Create `terraform/modules/compute` — the main application compute layer. This provisions the ECS cluster, ALB, API task definition and service, IAM roles, and CPU-based auto-scaling. The Qdrant ECS service is handled separately in the qdrant module; this module only manages the API + worker services.

## Context
- @.gsd/phases/6/RESEARCH.md — ECS Fargate + ALB patterns, IAM role split
- @terraform/modules/network/outputs.tf — ALB/API SGs, public/private subnets
- @terraform/modules/registry/outputs.tf — ECR repository URL for task definition

## Tasks

<task type="auto">
  <name>Create IAM roles and ECS cluster</name>
  <files>
    terraform/modules/compute/main.tf
    terraform/modules/compute/variables.tf
    terraform/modules/compute/outputs.tf
  </files>
  <action>
    Create `terraform/modules/compute/variables.tf`:
    ```hcl
    variable "project"           { type = string }
    variable "environment"       { type = string }
    variable "aws_region"        { type = string }
    variable "aws_account_id"    { type = string }

    variable "vpc_id"            { type = string }
    variable "public_subnet_ids" { type = list(string) }
    variable "private_subnet_ids"{ type = list(string) }
    variable "alb_sg_id"         { type = string }
    variable "api_sg_id"         { type = string }

    variable "ecr_repository_url" { type = string }
    variable "image_tag"          { type = string; default = "latest" }

    variable "certificate_arn"    { type = string }  # ACM cert for HTTPS ALB

    variable "api_cpu"            { type = number; default = 512 }
    variable "api_memory"         { type = number; default = 1024 }
    variable "api_desired_count"  { type = number; default = 1 }
    variable "api_min_count"      { type = number; default = 1 }
    variable "api_max_count"      { type = number; default = 4 }

    variable "env_vars"           { type = map(string); default = {} }  # app-level env vars
    variable "secrets"            { type = map(string); default = {} }  # Secrets Manager ARNs
    ```

    Create `terraform/modules/compute/main.tf` in logical sections:

    **Data Sources:**
    ```hcl
    data "aws_iam_policy_document" "ecs_assume_role" {
      statement {
        effect  = "Allow"
        actions = ["sts:AssumeRole"]
        principals {
          type        = "Service"
          identifiers = ["ecs-tasks.amazonaws.com"]
        }
      }
    }
    ```

    **IAM — Execution Role** (ECS agent permissions — pull ECR, push CloudWatch):
    ```hcl
    resource "aws_iam_role" "execution_role" {
      name               = "${var.project}-${var.environment}-ecs-execution"
      assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
    }
    resource "aws_iam_role_policy_attachment" "execution_role_policy" {
      role       = aws_iam_role.execution_role.name
      policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
    }
    ```

    **IAM — Task Role** (application permissions — extend as needed):
    ```hcl
    resource "aws_iam_role" "task_role" {
      name               = "${var.project}-${var.environment}-ecs-task"
      assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
    }
    # Inline policy: allow SSM GetParameter for future secrets
    resource "aws_iam_role_policy" "task_role_policy" {
      name = "ssm-params"
      role = aws_iam_role.task_role.id
      policy = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Effect   = "Allow"
          Action   = ["ssm:GetParameters", "secretsmanager:GetSecretValue"]
          Resource = ["arn:aws:ssm:${var.aws_region}:${var.aws_account_id}:parameter/${var.project}/${var.environment}/*"]
        }]
      })
    }
    ```

    **ECS Cluster:**
    ```hcl
    resource "aws_ecs_cluster" "main" {
      name = "${var.project}-${var.environment}"
      setting {
        name  = "containerInsights"
        value = "enabled"
      }
    }
    ```

    **ALB:**
    - `aws_lb` (internal=false, public subnets, alb_sg)
    - `aws_lb_target_group` for API: port 8000, protocol HTTP, target_type="ip", health_check path="/health"
    - `aws_lb_listener` HTTP/80: redirect to HTTPS 301
    - `aws_lb_listener` HTTPS/443: forward to target group, `certificate_arn = var.certificate_arn`

    **CloudWatch Log Group:**
    ```hcl
    resource "aws_cloudwatch_log_group" "api" {
      name              = "/ecs/${var.project}-${var.environment}/api"
      retention_in_days = 30
    }
    ```

    **ECS Task Definition** (Fargate, awsvpc, cpu=var.api_cpu, memory=var.api_memory):
    - execution_role_arn = execution_role ARN
    - task_role_arn = task_role ARN
    - Container: image="${var.ecr_repository_url}:${var.image_tag}", port 8000
    - Environment from `var.env_vars` (converted: [for k,v in var.env_vars: {name=k, value=v}])
    - logConfiguration: awslogs driver → log group above

    **ECS Service:**
    - cluster, task_definition, desired_count = var.api_desired_count
    - launch_type = "FARGATE"
    - network_configuration: private subnets, api_sg
    - load_balancer: target_group_arn, container_name="api", container_port=8000
    - deployment_circuit_breaker { enable = true, rollback = true }

    **Auto-scaling:**
    ```hcl
    resource "aws_appautoscaling_target" "api" {
      service_namespace  = "ecs"
      resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
      scalable_dimension = "ecs:service:DesiredCount"
      min_capacity       = var.api_min_count
      max_capacity       = var.api_max_count
    }
    resource "aws_appautoscaling_policy" "api_cpu" {
      name               = "${var.project}-${var.environment}-cpu-tracking"
      service_namespace  = "ecs"
      resource_id        = aws_appautoscaling_target.api.resource_id
      scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
      policy_type        = "TargetTrackingScaling"
      target_tracking_scaling_policy_configuration {
        predefined_metric_specification {
          predefined_metric_type = "ECSServiceAverageCPUUtilization"
        }
        target_value       = 70.0
        scale_in_cooldown  = 300
        scale_out_cooldown = 60
      }
    }
    ```

    Create `terraform/modules/compute/outputs.tf`:
    ```hcl
    output "ecs_cluster_id"     { value = aws_ecs_cluster.main.id }
    output "ecs_cluster_name"   { value = aws_ecs_cluster.main.name }
    output "execution_role_arn" { value = aws_iam_role.execution_role.arn }
    output "task_role_arn"      { value = aws_iam_role.task_role.arn }
    output "alb_dns_name"       { value = aws_lb.api.dns_name }
    output "alb_zone_id"        { value = aws_lb.api.zone_id }
    output "api_service_name"   { value = aws_ecs_service.api.name }
    ```
  </action>
  <verify>cd terraform/modules/compute && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0; ECS cluster, ALB with HTTPS+redirect, task def, auto-scaling, and IAM roles all defined</done>
</task>

## Success Criteria
- [ ] `terraform validate` passes in `terraform/modules/compute/`
- [ ] IAM: two roles — `execution_role` (ECS agent) + `task_role` (app)
- [ ] ALB: HTTP/80 redirects to HTTPS/443; HTTPS forwards to target group
- [ ] Target group `target_type = "ip"` (Fargate requirement)
- [ ] Auto-scaling on CPU 70% with circuit breaker on ECS service
