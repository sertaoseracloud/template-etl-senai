output "glue_job_name" {
  description = "Name of the Glue job"
  value       = module.glue-job.job_name
}

output "iam_role_arn" {
  description = "ARN of the IAM role for Glue"
  value       = module.iam-role.role_arn
}

output "raw_bucket_name" {
  description = "Name of the raw S3 bucket"
  value       = module.s3-buckets.raw_bucket_name
}

output "curated_bucket_name" {
  description = "Name of the curated S3 bucket"
  value       = module.s3-buckets.curated_bucket_name
}

output "glue_database_name" {
  description = "Name of the Glue database"
  value       = module.catalog-table.database_name
}

output "glue_table_name" {
  description = "Name of the Glue table"
  value       = module.catalog-table.table_name
}
