# EventBridge rule to capture S3 ObjectCreated events via CloudTrail
resource "aws_cloudwatch_event_rule" "s3_object_created" {
  name           = "${var.project_name}-s3-object-created"
  description    = "Capture S3 ObjectCreated events for ${var.raw_bucket_name}"
  event_pattern  = jsonencode({
    source : ["aws.s3"],
    "detail-type" : ["AWS API Call via CloudTrail"],
    detail : {
      eventSource : ["aws.s3"],
      eventName : ["PutObject", "CompleteMultipartUpload"],
      requestParameters : {
        bucketName : [var.raw_bucket_name]
      }
    }
  })
}

# IAM role for EventBridge to invoke Glue job
resource "aws_iam_role" "eventbridge_to_glue" {
  name = "${var.project_name}-eventbridge-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

# Policy allowing EventBridge to invoke StartJobRun on the specific Glue job
resource "aws_iam_role_policy" "eventbridge_glue_invoke" {
  role = aws_iam_role.eventbridge_to_glue.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun"
        ]
        Resource = var.glue_job_arn
      }
    ]
  })
}

# EventBridge target to invoke Glue job with Input Transformer
resource "aws_cloudwatch_event_target" "glue_job" {
  rule           = aws_cloudwatch_event_rule.s3_object_created.name
  target_id      = "${var.project_name}-glue-job-target"
  arn            = "arn:aws:glue:${data.aws_region.current.name}:${data.aws_account_id.current}:job/${var.project_name}-csv-to-parquet"
  role_arn       = aws_iam_role.eventbridge_to_glue.arn

  input_transformer {
    input_template = "\"--file-key\", \"<s3-key>\""
    input_paths = {
      "s3-key" = "$.detail.requestParameters.key"
    }
  }
}

# S3 bucket notification to send events to EventBridge
resource "aws_s3_bucket_notification" "to_eventbridge" {
  bucket = var.raw_bucket_name

  eventbridge_configuration {
    event_rule = aws_cloudwatch_event_rule.s3_object_created.name
    suffix     = var.prefix
  }
}

# Data sources for AWS region and account ID
data "aws_region" "current" {
  name = ""
}

data "aws_account_id" "current" {
  id = ""
}
