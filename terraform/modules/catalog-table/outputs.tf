output "database_name" {
  description = "Name of the Glue database"
  value       = aws_glue_catalog_database.this.name
}

output "table_name" {
  description = "Name of the Glue table"
  value       = aws_glue_catalog_table.this.name
}

output "database_arn" {
  description = "ARN of the Glue database"
  value       = aws_glue_catalog_database.this.arn
}

output "table_arn" {
  description = "ARN of the Glue table"
  value       = aws_glue_catalog_table.this.arn
}

output "partition_count" {
  description = "Number of partitions created"
  value       = length(aws_glue_partition.this)
}
