variable "project" {
  type        = string
  description = "Project name used in resource naming"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, production)"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "CIDR block for the VPC"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
  description = "CIDR blocks for public subnets (one per AZ)"
}

variable "private_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
  description = "CIDR blocks for private subnets (one per AZ)"
}

variable "azs" {
  type        = list(string)
  description = "Availability zones to deploy into (e.g. [\"us-east-1a\", \"us-east-1b\"])"
}
