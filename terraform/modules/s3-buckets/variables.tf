variable "raw_bucket_name" {
  description = "Name of the raw S3 bucket"
  type        = string
}

variable "curated_bucket_name" {
  description = "Name of the curated S3 bucket"
  type        = string
}

variable "environment" {
  description = "Environment name for resource tagging"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
}
