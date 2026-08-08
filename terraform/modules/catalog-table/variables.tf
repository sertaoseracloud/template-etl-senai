variable "database_name" {
  description = "Name of the Glue database"
  type        = string
}

variable "database_description" {
  description = "Description of the Glue database"
  type        = string
}

variable "glue_version" {
  description = "Glue version"
  type        = string
}

variable "schema_path" {
  description = "Path to the schema JSON file"
  type        = string
}

variable "curated_bucket_name" {
  description = "Name of the curated S3 bucket"
  type        = string
}
