output "primary_endpoint" {
  description = "Redis primary endpoint address (write)"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "reader_endpoint" {
  description = "Redis reader endpoint address (read)"
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "port" {
  description = "Redis port"
  value       = 6379
}

output "replication_group_id" {
  description = "ElastiCache replication group ID"
  value       = aws_elasticache_replication_group.redis.id
}
