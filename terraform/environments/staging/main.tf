terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket       = "REPLACE_WITH_BOOTSTRAP_OUTPUT"
    key          = "staging/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" { region = var.aws_region }

module "network" {
  source      = "../../modules/network"
  project     = var.project
  environment = var.environment
  azs         = var.azs
}

module "registry" {
  source      = "../../modules/registry"
  project     = var.project
  environment = var.environment
}

module "redis" {
  source             = "../../modules/redis"
  project            = var.project
  environment        = var.environment
  subnet_ids         = module.network.private_subnet_ids
  redis_sg_id        = module.network.redis_sg_id
  node_type          = var.redis_node_type
  num_cache_clusters = var.redis_num_clusters
  automatic_failover = var.redis_automatic_failover
  multi_az           = var.redis_multi_az
}

module "compute" {
  source             = "../../modules/compute"
  project            = var.project
  environment        = var.environment
  aws_region         = var.aws_region
  aws_account_id     = var.aws_account_id
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids
  alb_sg_id          = module.network.alb_sg_id
  api_sg_id          = module.network.api_sg_id
  ecr_repository_url = module.registry.repository_url
  image_tag          = var.image_tag
  certificate_arn    = var.certificate_arn
  api_cpu            = var.api_cpu
  api_memory         = var.api_memory
  api_desired_count  = var.api_desired_count
  api_min_count      = var.api_min_count
  api_max_count      = var.api_max_count
}

module "qdrant" {
  source             = "../../modules/qdrant"
  project            = var.project
  environment        = var.environment
  aws_region         = var.aws_region
  private_subnet_ids = module.network.private_subnet_ids
  qdrant_sg_id       = module.network.qdrant_sg_id
  efs_sg_id          = module.network.efs_sg_id
  ecs_cluster_id     = module.compute.ecs_cluster_id
  execution_role_arn = module.compute.execution_role_arn
  desired_count      = var.qdrant_desired_count
  cpu                = var.qdrant_cpu
  memory             = var.qdrant_memory
}

module "observability" {
  source           = "../../modules/observability"
  project          = var.project
  environment      = var.environment
  ecs_cluster_name = module.compute.ecs_cluster_name
  api_service_name = module.compute.api_service_name
  alb_arn_suffix   = module.compute.alb_arn_suffix
  tg_arn_suffix    = module.compute.tg_arn_suffix
  alarm_email      = var.alarm_email
}

output "alb_dns_name" { value = module.compute.alb_dns_name }
output "ecr_repository_url" { value = module.registry.repository_url }
