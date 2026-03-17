variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "image_tag_mutability" {
  type        = string
  default     = "MUTABLE"
  description = "Tag mutability: MUTABLE or IMMUTABLE (use IMMUTABLE in production)"
}

variable "scan_on_push" {
  type        = bool
  default     = true
  description = "Enable image vulnerability scanning on push"
}

variable "lifecycle_policy_count" {
  type        = number
  default     = 10
  description = "Number of tagged images to retain"
}
