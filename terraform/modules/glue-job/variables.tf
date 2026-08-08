variable "job_name" {
  description = "Name of the Glue job"
  type        = string
}

variable "glue_version" {
  description = "Glue version"
  type        = string
}

variable "worker_type" {
  description = "Glue worker type"
  type        = string
}

variable "timeout_minutes" {
  description = "Job timeout in minutes"
  type        = number
}

variable "number_of_workers" {
  description = "Number of workers"
  type        = number
}

variable "python_version" {
  description = "Python version"
  type        = string
}

variable "role_arn" {
  description = "IAM role ARN for the job"
  type        = string
}

variable "raw_bucket_name" {
  description = "Raw S3 bucket name"
  type        = string
}

variable "curated_bucket_name" {
  description = "Curated S3 bucket name"
  type        = string
}

variable "schema_location" {
  description = "Schema location path within curated bucket"
  type        = string
}

variable "script_path" {
  description = "Path to the Glue job script"
  type        = string
}
