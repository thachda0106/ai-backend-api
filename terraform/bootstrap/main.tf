# Bootstrap: run this ONCE per AWS account to create the Terraform remote state S3 bucket.
#
# After running, copy the `state_bucket_name` output into each environment's
# backend "s3" { bucket = "..." } block.
#
# Usage:
#   cd terraform/bootstrap
#   terraform init
#   terraform apply \
#     -var="aws_region=us-east-1" \
#     -var="project=ai-backend-api"

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type        = string
  description = "Project name (used in S3 bucket name)"
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${var.project}-tfstate-${data.aws_caller_identity.current.account_id}"
}

# S3 bucket for Terraform remote state
resource "aws_s3_bucket" "tfstate" {
  bucket        = local.bucket_name
  force_destroy = false # Safety: prevent accidental destruction of state

  tags = {
    Purpose = "Terraform remote state"
    Project = var.project
  }
}

# Versioning — enables state history and rollback
resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Encryption at rest
resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "state_bucket_name" {
  description = "Copy this into each environment's backend block (bucket = ...)"
  value       = local.bucket_name
}

output "state_bucket_arn" {
  value = aws_s3_bucket.tfstate.arn
}
