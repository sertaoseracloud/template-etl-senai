variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "raw_bucket_name" {
  description = "S3 raw bucket name"
  type        = string
}

variable "glue_job_arn" {
  description = "ARN of the Glue job to invoke"
  type        = string
}

variable "prefix" {
  description = "S3 key prefix to watch (e.g., temperaturas/)"
  type        = string
  default     = "temperaturas/"
}
