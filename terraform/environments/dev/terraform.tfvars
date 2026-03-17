project     = "ai-backend-api"
environment = "dev"
aws_region  = "us-east-1"
azs         = ["us-east-1a", "us-east-1b"]
# aws_account_id: set via TF_VAR_aws_account_id env var (never commit account IDs)
certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/REPLACE_ME"

# Redis — single-node, smallest instance
redis_node_type          = "cache.t3.micro"
redis_num_clusters       = 1
redis_automatic_failover = false
redis_multi_az           = false

# API — minimal resources for dev
api_cpu           = 256
api_memory        = 512
api_desired_count = 1
api_min_count     = 1
api_max_count     = 2

# Qdrant — minimal resources for dev
qdrant_desired_count = 1
qdrant_cpu           = 512
qdrant_memory        = 1024

alarm_email = ""
