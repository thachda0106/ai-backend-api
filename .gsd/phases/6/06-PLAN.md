---
phase: 6
plan: 6
wave: 3
depends_on: [6.5]
files_modified:
  - terraform/modules/observability/main.tf
  - terraform/modules/observability/variables.tf
  - terraform/modules/observability/outputs.tf
autonomous: true

must_haves:
  truths:
    - "CloudWatch alarms for CPU, memory, and 5xx errors defined"
    - "SNS topic created for alarm notifications"
    - "Log metric filter for 5xx errors on the API log group"
---

# Plan 6.6: Observability Module (CloudWatch + SNS)

## Objective
Create `terraform/modules/observability` — CloudWatch alarms for ECS CPU utilisation, ECS memory utilisation, and ALB 5xx error rate. All alarms notify an SNS topic. The log groups themselves are created in their respective modules (compute creates `/ecs/.../api`, qdrant creates `/ecs/.../qdrant`); this module references them by name.

## Context
- @.gsd/phases/6/RESEARCH.md — observability requirements
- @terraform/modules/compute/outputs.tf — ecs_cluster_name, api_service_name for alarm dimensions

## Tasks

<task type="auto">
  <name>Create CloudWatch alarms and SNS topic</name>
  <files>
    terraform/modules/observability/main.tf
    terraform/modules/observability/variables.tf
    terraform/modules/observability/outputs.tf
  </files>
  <action>
    Create `terraform/modules/observability/variables.tf`:
    ```hcl
    variable "project"          { type = string }
    variable "environment"      { type = string }

    variable "ecs_cluster_name" { type = string }
    variable "api_service_name" { type = string }
    variable "alb_arn_suffix"   { type = string }          # aws_lb.api.arn_suffix
    variable "tg_arn_suffix"    { type = string }          # aws_lb_target_group.api.arn_suffix

    variable "alarm_email"      { type = string; default = "" }  # SNS subscription email (optional)
    variable "cpu_threshold"    { type = number; default = 80 }
    variable "memory_threshold" { type = number; default = 80 }
    variable "error_5xx_threshold" { type = number; default = 5 } # count per minute
    ```

    Create `terraform/modules/observability/main.tf`:

    **SNS Topic:**
    ```hcl
    resource "aws_sns_topic" "alarms" {
      name = "${var.project}-${var.environment}-alarms"
    }
    resource "aws_sns_topic_subscription" "email" {
      count     = var.alarm_email != "" ? 1 : 0
      topic_arn = aws_sns_topic.alarms.arn
      protocol  = "email"
      endpoint  = var.alarm_email
    }
    ```

    **ECS CPU Alarm:**
    ```hcl
    resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
      alarm_name          = "${var.project}-${var.environment}-ecs-cpu-high"
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 2
      metric_name         = "CPUUtilization"
      namespace           = "AWS/ECS"
      period              = 60
      statistic           = "Average"
      threshold           = var.cpu_threshold
      alarm_description   = "ECS CPU utilisation > ${var.cpu_threshold}%"
      alarm_actions       = [aws_sns_topic.alarms.arn]
      ok_actions          = [aws_sns_topic.alarms.arn]
      dimensions = {
        ClusterName = var.ecs_cluster_name
        ServiceName = var.api_service_name
      }
    }
    ```

    **ECS Memory Alarm:** same pattern, metric_name = "MemoryUtilization", threshold = var.memory_threshold

    **ALB 5xx Alarm** (HTTP errors from target — not just ALB):
    ```hcl
    resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
      alarm_name          = "${var.project}-${var.environment}-alb-5xx"
      comparison_operator = "GreaterThanThreshold"
      evaluation_periods  = 1
      metric_name         = "HTTPCode_Target_5XX_Count"
      namespace           = "AWS/ApplicationELB"
      period              = 60
      statistic           = "Sum"
      threshold           = var.error_5xx_threshold
      alarm_description   = "ALB 5xx errors > ${var.error_5xx_threshold} per minute"
      treat_missing_data  = "notBreaching"
      alarm_actions       = [aws_sns_topic.alarms.arn]
      dimensions = {
        LoadBalancer = var.alb_arn_suffix
        TargetGroup  = var.tg_arn_suffix
      }
    }
    ```

    Create `terraform/modules/observability/outputs.tf`:
    ```hcl
    output "sns_topic_arn" { value = aws_sns_topic.alarms.arn }
    ```
  </action>
  <verify>cd terraform/modules/observability && terraform init -backend=false && terraform validate</verify>
  <done>terraform validate exits 0; SNS topic + 3 CloudWatch alarms (CPU, memory, 5xx) defined</done>
</task>

## Success Criteria
- [ ] `terraform validate` passes in `terraform/modules/observability/`
- [ ] SNS topic with optional email subscription
- [ ] 3 alarms: ECS CPU, ECS memory, ALB 5xx
- [ ] `treat_missing_data = "notBreaching"` on 5xx alarm (no false positives during quiet periods)
