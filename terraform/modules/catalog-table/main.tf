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

  partition_keys = [
    for key in local.schema.partition_keys : {
      name = key.name
      type = key.type
    }
  ]

  storage_descriptor {
    location = "s3://${var.curated_bucket_name}/${local.schema.location}"

    input_format  = local.schema.storage.input_format
    output_format = local.schema.storage.output_format

    serde_info {
      serialization_library = local.schema.storage.serde
    }

    columns = [
      for col in local.schema.columns : {
        name = col.name
        type = col.type
        comment = lookup(col, "comment", "")
      }
    ]
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

    serde_info {
      serialization_library = local.schema.storage.serde
    }

    columns = [
      for col in local.schema.columns : {
        name = col.name
        type = col.type
        comment = lookup(col, "comment", "")
      }
    ]
  }

  depends_on = [
    aws_glue_catalog_table.this
  ]
}

data "aws_caller_identity" "current" {}
