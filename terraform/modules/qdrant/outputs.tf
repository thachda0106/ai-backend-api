output "efs_id" {
  description = "EFS file system ID used for Qdrant storage"
  value       = aws_efs_file_system.qdrant.id
}

output "service_name" {
  description = "ECS service name for Qdrant"
  value       = aws_ecs_service.qdrant.name
}

output "rest_port" {
  description = "Qdrant REST API port"
  value       = 6333
}

output "grpc_port" {
  description = "Qdrant gRPC port"
  value       = 6334
}
