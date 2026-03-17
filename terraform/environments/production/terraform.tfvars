project         = "ai-backend-api"
environment     = "production"
aws_region      = "us-east-1"
azs             = ["us-east-1a", "us-east-1b"]
certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/REPLACE_ME"

# Redis — production-grade with Multi-AZ failover
redis_node_type          = "cache.r7g.large"
redis_num_clusters       = 2
redis_automatic_failover = true
redis_multi_az           = true

# API — production resources with horizontal scaling
api_cpu           = 1024
api_memory        = 2048
api_desired_count = 2
api_min_count     = 2
api_max_count     = 8

# Qdrant — production resources
qdrant_desired_count = 1
qdrant_cpu           = 2048
qdrant_memory        = 4096

alarm_email = "" # Replace with your ops email
