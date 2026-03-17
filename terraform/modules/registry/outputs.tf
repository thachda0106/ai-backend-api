output "repository_url" {
  description = "Full ECR repository URL (used in ECS task definitions)"
  value       = aws_ecr_repository.api.repository_url
}

output "repository_arn" {
  description = "ECR repository ARN"
  value       = aws_ecr_repository.api.arn
}

output "repository_name" {
  description = "ECR repository name"
  value       = aws_ecr_repository.api.name
}
