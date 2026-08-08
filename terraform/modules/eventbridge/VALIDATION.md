# EventBridge Infrastructure Validation

This document describes how the EventBridge infrastructure from Phase 5 is validated and how it integrates with the local performance testing workflow.

## Local Validation via `./run.sh watch`

The local development environment simulates EventBridge behavior using `./run.sh watch`:

```bash
# Start the emulator and watch for new files
./run.sh up
./run.sh watch
```

**How it works:**

1. `s3_watch.py` polls the S3 bucket at regular intervals (default: 5 seconds)
2. When a new file is detected under `temperaturas/` prefix, it extracts the file key
3. The script invokes `job.py` with `--file-key <s3-key>` to process the new file
4. This mirrors the EventBridge Input Transformer pattern (see below)

**Local validation is equivalent to EventBridge because:**

- Both trigger on new files in `temperaturas/` prefix
- Both pass `--file-key` to the Glue job
- Both result in the same ETL transformation (read CSV -> add cidade_key -> derive temp_media -> write Parquet)

## Real AWS EventBridge Configuration

In production AWS, the following EventBridge rule captures S3 ObjectCreated events:

### CloudTrail-Based Event Pattern

```hcl
resource "aws_cloudwatch_event_rule" "s3_object_created" {
  event_pattern = jsonencode({
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
```

### S3 Bucket Notification

```hcl
resource "aws_s3_bucket_notification" "to_eventbridge" {
  bucket = var.raw_bucket_name
  eventbridge_configuration {
    event_rule = aws_cloudwatch_event_rule.s3_object_created.name
    suffix     = var.prefix  # "temperaturas/"
  }
}
```

## Input Transformer Configuration

The Input Transformer extracts the S3 key from the CloudTrail event and transforms it into Glue job arguments:

```hcl
resource "aws_cloudwatch_event_target" "glue_job" {
  input_transformer {
    input_template = "\"--file-key\", \"<s3-key>\""
    input_paths = {
      "s3-key" = "$.detail.requestParameters.key"
    }
  }
}
```

### JSONPath Expression Explained

| Expression | Description |
|-----------|-------------|
| `$.detail.requestParameters.key` | Navigates to the S3 object key in the CloudTrail event |

**CloudTrail Event Structure:**

```json
{
  "detail": {
    "requestParameters": {
      "bucketName": "project-raw",
      "key": "temperaturas/test.csv"
    }
  }
}
```

### Input Transformer Transformation

| Input (CloudTrail) | Output (Glue Job Args) |
|-------------------|----------------------|
| `$.detail.requestParameters.key` = `"temperaturas/test.csv"` | `"--file-key", "temperaturas/test.csv"` |

## IAM Policy for EventBridge-to-Glue

The IAM role allows EventBridge to invoke the specific Glue job:

```hcl
resource "aws_iam_role_policy" "eventbridge_glue_invoke" {
  policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Action = ["glue:StartJobRun", "glue:GetJobRun"]
      Resource = var.glue_job_arn
    }]
  })
}
```

This restricts EventBridge to invoke ONLY the csv-to-parquet job (EVT-05).

## Validation Checklist

- [ ] `aws_cloudwatch_event_rule` captures S3 ObjectCreated events (EVT-03)
- [ ] EventBridge rule targets Glue job with Input Transformer (EVT-04)
- [ ] IAM policy restricts to specific job ARN (EVT-05)
- [ ] Local `watch` loop validates the same trigger mechanism
- [ ] Performance test (`./run.sh perf-test`) exercises the full pipeline

## Files

| File | Purpose |
|------|---------|
| `main.tf` | EventBridge rule, target, IAM role, S3 notification |
| `variables.tf` | Input variables: project_name, raw_bucket_name, glue_job_arn, prefix |
| `outputs.tf` | Exports: eventbridge_role_arn |
| `VALIDATION.md` | This document |

## Requirements Coverage

| Requirement | Description | Covered By |
|------------|-------------|------------|
| EVT-03 | EventBridge rule targets Glue job | `aws_cloudwatch_event_rule` + `aws_cloudwatch_event_target` |
| EVT-04 | Input Transformer extracts S3 key | `input_transformer` block with JSONPath |
| EVT-05 | IAM policy restricts to specific job | `aws_iam_role_policy` with `var.glue_job_arn` |
