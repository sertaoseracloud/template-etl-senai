provider "aws" {
  region = var.aws_region
}

locals {
  # Derive bucket and database names using the same logic as catalog/config.py
  # raw_bucket()      = f"{PROJECT_NAME.replace('_', '-')}-raw"
  # curated_bucket()  = f"{PROJECT_NAME.replace('_', '-')}-curated"
  # database_name()   = f"{PROJECT_NAME.replace('-', '_')}_db"
  project_name_slug = replace(var.project_name, "_", "-")
  project_name_underscore = replace(var.project_name, "-", "_")

  raw_bucket_name    = "${local.project_name_slug}-${var.s3_raw_bucket_suffix}"
  curated_bucket_name = "${local.project_name_slug}-${var.s3_curated_bucket_suffix}"
  database_name      = "${local.project_name_underscore}_db"
}

module "s3-buckets" {
  source = "./modules/s3-buckets"

  raw_bucket_name    = local.raw_bucket_name
  curated_bucket_name = local.curated_bucket_name
}

module "iam-role" {
  source = "./modules/iam-role"

  role_name      = "${var.project_name}-glue-role"
  raw_bucket_arn = module.s3-buckets.raw_bucket_arn
  curated_bucket_arn = module.s3-buckets.curated_bucket_arn
}

module "catalog-table" {
  source = "./modules/catalog-table"

  database_name       = local.database_name
  database_description = "Temperature data for Santa Catarina cities"
  glue_version        = var.glue_version
  schema_path         = "${path.module}/../catalog/schema/temperaturas.json"
  curated_bucket_name = local.curated_bucket_name
}

module "glue-job" {
  source = "./modules/glue-job"

  job_name                     = "${var.project_name}-csv-to-parquet"
  glue_version                 = var.glue_version
  worker_type                  = var.glue_worker_type
  timeout_minutes              = var.glue_timeout_minutes
  number_of_workers            = var.glue_number_of_workers
  python_version               = var.glue_python_version
  role_arn                     = module.iam-role.role_arn
  raw_bucket_name              = local.raw_bucket_name
  curated_bucket_name          = local.curated_bucket_name
  schema_location              = "temperaturas/"
  script_path                  = "jobs/csv_to_parquet/job.py"
}
