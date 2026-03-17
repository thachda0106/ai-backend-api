output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "alb_sg_id" {
  description = "Security group ID for the Application Load Balancer"
  value       = aws_security_group.alb.id
}

output "api_sg_id" {
  description = "Security group ID for the API ECS tasks"
  value       = aws_security_group.api.id
}

output "redis_sg_id" {
  description = "Security group ID for ElastiCache Redis"
  value       = aws_security_group.redis.id
}

output "qdrant_sg_id" {
  description = "Security group ID for Qdrant ECS tasks"
  value       = aws_security_group.qdrant.id
}

output "efs_sg_id" {
  description = "Security group ID for EFS mount targets"
  value       = aws_security_group.efs.id
}
