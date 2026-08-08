resource "aws_glue_job" "this" {
  name     = var.job_name
  role_arn = var.role_arn
  glue_version = var.glue_version
  worker_type  = var.worker_type
  timeout      = var.timeout_minutes
  number_of_workers = var.number_of_workers

  command {
    name            = "pythonshell"
    python_version  = var.python_version
    script_location = "s3://${var.raw_bucket_name}/${var.script_path}"
  }

  default_arguments = merge({
    "--raw_bucket"       = var.raw_bucket_name
    "--curated_bucket"   = var.curated_bucket_name
    "--schema_location"  = var.schema_location
    "--enable-metrics"   = "true"
    "--enable-continuous-logging" = "true"
    "--file-key"         = var.default_file_key
  }, var.default_arguments)

  execution_property {
    max_concurrent_runs = 1
  }
}
