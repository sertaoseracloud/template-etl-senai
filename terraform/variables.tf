variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "template_etl"
}

variable "environment" {
  description = "Environment name for resource tagging (e.g., production, staging, dev)"
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "glue_version" {
  description = "Glue version for job"
  type        = string
  default     = "5.0"
}

variable "glue_worker_type" {
  description = "Glue worker type"
  type        = string
  default     = "G.1X"
}

variable "glue_timeout_minutes" {
  description = "Glue job timeout in minutes"
  type        = number
  default     = 10
}

variable "glue_number_of_workers" {
  description = "Number of Glue workers"
  type        = number
  default     = 2
}

variable "glue_python_version" {
  description = "Python version for Glue job"
  type        = string
  default     = "3.11"
}

variable "s3_raw_bucket_suffix" {
  description = "Suffix for raw S3 bucket name"
  type        = string
  default     = "raw"
}

variable "s3_curated_bucket_suffix" {
  description = "Suffix for curated S3 bucket name"
  type        = string
  default     = "curated"
}
