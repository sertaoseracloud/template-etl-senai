variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "raw_bucket_arn" {
  description = "ARN of the raw S3 bucket"
  type        = string
}

variable "curated_bucket_arn" {
  description = "ARN of the curated S3 bucket"
  type        = string
}
