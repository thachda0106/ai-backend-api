project         = "ai-backend-api"
environment     = "staging"
aws_region      = "us-east-1"
azs             = ["us-east-1a", "us-east-1b"]
certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/REPLACE_ME"

# Redis — primary + replica, no multi-AZ
redis_node_type          = "cache.t3.small"
redis_num_clusters       = 2
redis_automatic_failover = true
redis_multi_az           = false

# API — moderate resources
api_cpu           = 512
api_memory        = 1024
api_desired_count = 1
api_min_count     = 1
api_max_count     = 4

# Qdrant — moderate resources
qdrant_desired_count = 1
qdrant_cpu           = 1024
qdrant_memory        = 2048

alarm_email = ""
