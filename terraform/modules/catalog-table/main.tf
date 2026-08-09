locals {
  schema = jsondecode(file(var.schema_path))
}

resource "aws_glue_catalog_database" "this" {
  name        = var.database_name
  description = var.database_description
}

resource "aws_glue_catalog_table" "this" {
  name          = local.schema.table
  database_name = aws_glue_catalog_database.this.name
  catalog_id    = data.aws_caller_identity.current.account_id

  table_type = "EXTERNAL_TABLE"

  parameters = merge(
    local.schema.table_parameters,
    { "parquet.compression" = "SNAPPY" }
  )

  dynamic "partition_keys" {
    for_each = local.schema.partition_keys
    content {
      name = partition_keys.value.name
      type = partition_keys.value.type
    }
  }

  storage_descriptor {
    location = "s3://${var.curated_bucket_name}/${local.schema.location}"

    input_format  = local.schema.storage.input_format
    output_format = local.schema.storage.output_format

    ser_de_info {
      serialization_library = local.schema.storage.serde
    }

    dynamic "columns" {
      for_each = local.schema.columns
      content {
        name    = columns.value.name
        type    = columns.value.type
        comment = lookup(columns.value, "comment", "")
      }
    }
  }
}

resource "aws_glue_partition" "this" {
  count = length(local.schema.partitions)

  database_name = aws_glue_catalog_database.this.name
  table_name    = aws_glue_catalog_table.this.name

  partition_values = local.schema.partitions[count.index].values

  storage_descriptor {
    location = "s3://${var.curated_bucket_name}/${local.schema.location}${
      join("/", [
        for idx, key in local.schema.partition_keys :
        "${key.name}=${local.schema.partitions[count.index].values[idx]}"
      ])
    }/"

    input_format  = local.schema.storage.input_format
    output_format = local.schema.storage.output_format

    ser_de_info {
      serialization_library = local.schema.storage.serde
    }

    dynamic "columns" {
      for_each = local.schema.columns
      content {
        name    = columns.value.name
        type    = columns.value.type
        comment = lookup(columns.value, "comment", "")
      }
    }
  }

  depends_on = [
    aws_glue_catalog_table.this
  ]
}

data "aws_caller_identity" "current" {}
