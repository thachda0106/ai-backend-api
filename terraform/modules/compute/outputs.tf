output "ecs_cluster_id" {
  description = "ECS cluster ID"
  value       = aws_ecs_cluster.main.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "execution_role_arn" {
  description = "ECS task execution role ARN (shared with qdrant module)"
  value       = aws_iam_role.execution_role.arn
}

output "task_role_arn" {
  description = "ECS task role ARN for the API container"
  value       = aws_iam_role.task_role.arn
}

output "alb_dns_name" {
  description = "ALB DNS name for Route53 or direct access"
  value       = aws_lb.api.dns_name
}

output "alb_zone_id" {
  description = "ALB hosted zone ID (for Route53 alias records)"
  value       = aws_lb.api.zone_id
}

output "alb_arn_suffix" {
  description = "ALB ARN suffix (for CloudWatch alarm dimensions)"
  value       = aws_lb.api.arn_suffix
}

output "tg_arn_suffix" {
  description = "Target group ARN suffix (for CloudWatch alarm dimensions)"
  value       = aws_lb_target_group.api.arn_suffix
}

output "api_service_name" {
  description = "ECS API service name"
  value       = aws_ecs_service.api.name
}
