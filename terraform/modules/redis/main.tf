resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project}-${var.environment}-redis"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "${var.project}-${var.environment}-redis-subnet-group"
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${var.project}-${var.environment}-redis"
  description          = "Redis for ${var.project} ${var.environment}"

  engine         = "redis"
  engine_version = var.engine_version
  node_type      = var.node_type
  port           = 6379

  num_cache_clusters = var.num_cache_clusters

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [var.redis_sg_id]

  automatic_failover_enabled = var.automatic_failover
  multi_az_enabled           = var.multi_az

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  # auth_token is required when transit_encryption_enabled = true
  # Pass via TF_VAR_auth_token env var in CI — never hardcode
  auth_token = var.auth_token != "" ? var.auth_token : null

  snapshot_retention_limit = var.snapshot_retention
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "sun:05:00-sun:07:00"

  tags = {
    Name        = "${var.project}-${var.environment}-redis"
    Project     = var.project
    Environment = var.environment
  }
}
