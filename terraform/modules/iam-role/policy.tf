data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "aws_iam_policy" "this" {
  name        = "${var.role_name}-policy"
  description = "Least-privilege policy for Glue job accessing S3, CloudWatch Logs, and Glue Data Catalog"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          var.raw_bucket_arn,
          "${var.raw_bucket_arn}/*",
          var.curated_bucket_arn,
          "${var.curated_bucket_arn}/*"
        ]
      },
      {
        Sid    = "S3ListBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          var.raw_bucket_arn,
          var.curated_bucket_arn
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:${data.aws_partition.current.partition}:logs:*:*:*"
      },
      {
        Sid    = "GlueDataCatalog"
        Effect = "Allow"
        Action = [
          "glue:GetTable",
          "glue:GetPartitions",
          "glue:CreatePartition"
        ]
        Resource = [
          "arn:${data.aws_partition.current.partition}:glue:*:*:table/*/*",
          "arn:${data.aws_partition.current.partition}:glue:*:*:database/*",
          "arn:${data.aws_partition.current.partition}:glue:*:*:catalog"
        ]
      }
    ]
  })
}
