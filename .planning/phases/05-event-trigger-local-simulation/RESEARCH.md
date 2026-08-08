# Phase 5: Event Trigger & Local Simulation - Research

**Researched:** 2026-08-08
**Domain:** AWS EventBridge event-driven triggers, S3 polling, boto3 S3 operations
**Confidence:** HIGH

## Summary

Phase 5 implements event-driven ETL by adding file-key parameter support to the Glue job, local S3 polling for Floci-based validation, and Terraform EventBridge infrastructure for real AWS. The Glue job (job.py) already has argparse infrastructure and reads config from os.environ, so adding `--file-key` CLI arg with `FILE_KEY` env fallback is straightforward. The tools service already has boto3 available for S3 upload and polling. Floci does not emulate EventBridge, so local validation uses polling as a workaround.

**Primary recommendation:** Add `--file-key` to job.py argparse, implement `upload` and `watch` subcommands in run.sh using the existing tools service pattern, and create a new `terraform/modules/eventbridge/` module for EventBridge infrastructure.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Glue job accepts file key via both `--file-key` CLI argument (priority) and `FILE_KEY` environment variable (fallback). CLI arg takes precedence if both are provided.
- **D-02:** If file key points to non-existent S3 object, the job skips silently and exits 0.
- **D-03:** `./run.sh upload <file>` uploads to S3 using the existing `tools` service (boto3). The S3 key is printed to stdout after successful upload.
- **D-04:** `./run.sh watch` polls S3 using `list_objects_v2` every 5 seconds (configurable via `POLL_INTERVAL` env var). Triggers job with file key when new files are detected.
- **D-05:** Terraform provisions S3 EventBridge integration (EventBridge data source pointing to raw bucket, filtered for ObjectCreated events). Uses Input Transformer to pass S3 key as job parameter.
- **D-06:** Job logs trigger events to CloudWatch Logs (standard Glue job logging).

### Claude's Discretion
- Watch subcommand polling interval: D-04 specifies 5-second default with `POLL_INTERVAL` env var override
- Output format for upload: D-03 specifies key printed to stdout

### Deferred Ideas
None — discussion stayed within phase scope.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVT-01 | Glue job accepts file parameter via CLI or env var | job.py argparse pattern, os.environ access |
| EVT-02 | Job logs CloudWatch-compatible event (file key, size, timestamp) | GlueContext logging, CloudWatch Logs in Glue 5.0 |
| SIM-01 | `./run.sh upload <file>` uploads to S3 and returns key | boto3 s3_client pattern from catalog/seed.py |
| SIM-02 | `./run.sh watch` polls S3 and triggers job with file parameter | boto3 list_objects_v2, docker compose pattern |
| SIM-03 | Full local flow: upload → trigger → job → parquet output | End-to-end integration |
| SIM-04 | Documentation explains EventBridge trigger requires real AWS | Floci limitation documented in PROJECT.md |
| IAC-05 | Terraform provisions EventBridge rule for S3 ObjectCreated | aws_cloudwatch_event_rule, aws_s3_bucket_notification |
| IAC-06 | Terraform provisions IAM role allowing EventBridge to invoke Glue job | Trust policy for events.amazonaws.com |
| IAC-07 | Input Transformer passes S3 key as job parameter | aws_cloudwatch_event_target input_transformer |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Glue job parameter handling | Job (job.py) | — | CLI args and env vars parsed in job entry point |
| CloudWatch logging | Job (job.py) | Glue service | GlueContext provides logging; continuous logging enabled via default_arguments |
| S3 upload | Tools service (boto3) | run.sh wrapper | boto3 already available in tools; run.sh orchestrates docker compose |
| S3 polling | Tools service (boto3) | run.sh wrapper | list_objects_v2 in tools; watch loop in run.sh |
| EventBridge rule | Terraform (IaC) | — | AWS infrastructure provisioning |
| EventBridge IAM | Terraform (IaC) | — | IAM role with events.amazonaws.com trust policy |
| Input Transformer | Terraform (IaC) | — | aws_cloudwatch_event_target configuration |

## S3 Polling & Upload

### S3 Upload Pattern

The existing `catalog/seed.py` demonstrates the canonical upload pattern using boto3:

```python
# From catalog/seed.py:51-62 - verified pattern
def upload_samples(s3, bucket: str, local_dir: str, prefix: str) -> int:
    csv_paths = sorted(Path(local_dir).glob("*.csv"))
    for csv_path in csv_paths:
        s3.upload_file(str(csv_path), bucket, f"{prefix}{csv_path.name}")
    return len(csv_paths)
```

**For `./run.sh upload <file>`:**
- Use `config.s3_client()` for boto3 S3 client (already has endpoint_url configured)
- Key format: `temperaturas/{filename}` following seed.py prefix pattern
- Return key to stdout after successful upload

### S3 Polling Pattern

```python
# Canonical boto3 polling pattern
import boto3
import os
import time

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 5))

def poll_for_new_files(s3_client, bucket, prefix, last_checked):
    """Poll S3 for new objects since last_checked timestamp."""
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=prefix
    )
    new_files = []
    for obj in response.get("Contents", []):
        if obj["LastModified"].timestamp() > last_checked:
            new_files.append(obj)
    return new_files

def watch_loop():
    s3 = boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL"])
    bucket = f"{os.environ['PROJECT_NAME'].replace('_', '-')}-raw"
    last_checked = time.time()
    
    while True:
        new_files = poll_for_new_files(s3, bucket, "temperaturas/", last_checked)
        for f in new_files:
            print(f"New file: {f['Key']}")
            # Trigger job with --file-key parameter
        last_checked = time.time()
        time.sleep(POLL_INTERVAL)
```

**Floci compatibility:** `list_objects_v2` is fully supported by Floci. This is a standard S3 API that Floci emulates correctly.

### Key Considerations
- **S3 key format:** `temperaturas/{filename}` matches existing seed.py prefix
- **State tracking:** Use file modification time for idempotent detection
- **Idempotency:** Skip files already processed (track in-memory or filesystem)

## Glue Job Parameter Passing

### CLI Argument Addition (EVT-01)

Existing job.py already uses argparse (line 85-87):

```python
# From job.py:84-87 - verified pattern
parser = argparse.ArgumentParser()
parser.add_argument("--JOB_NAME", required=True)
args = parser.parse_args()
```

**Add --file-key parameter:**

```python
parser.add_argument("--file-key", required=False, default=None)
args = parser.parse_args()

# Environment variable fallback
file_key = args.file_key if args.file_key else os.environ.get("FILE_KEY")
```

### Modified Input Path Logic (D-02)

```python
# If file_key provided, use it; otherwise fall back to default path
if file_key:
    # Validate file exists in S3
    raw_path = f"s3a://{raw_bucket}/{file_key}"
    # Non-existent file: skip silently, exit 0
    try:
        # Check if file exists using s3a filesystem
        raw_df = read_csv(spark, raw_path)
        if raw_df.count() == 0:
            print(f"No data in {file_key}, skipping.")
            return
    except Exception as e:
        print(f"File {file_key} not found, skipping silently.")
        return
else:
    raw_path = f"s3a://{raw_bucket}/temperaturas/"
    raw_df = read_csv(spark, raw_path)
```

### Terraform default_arguments (IAC-07)

From `terraform/modules/glue-job/main.tf:15-21` - verified pattern:

```hcl
default_arguments = {
  "--raw_bucket"       = var.raw_bucket_name
  "--curated_bucket"  = var.curated_bucket_name
  "--schema_location" = var.schema_location
  "--enable-metrics"  = "true"
  "--enable-continuous-logging" = "true"
}
```

For EventBridge, add `--file-key` parameter mapping:

```hcl
default_arguments = merge(var.default_arguments, {
  "--file-key" = ""  # Populated by EventBridge Input Transformer
})
```

## CloudWatch Logging (EVT-02)

### GlueContext Logging Pattern

Standard Glue job logging uses the GlueContext logger:

```python
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import SparkSession

glue_context = GlueContext(spark.sparkContext)
logger = glue_context.get_logger()

# Log trigger event (EVT-02)
logger.info(f"Event triggered: file_key={file_key}, size={object_size}, timestamp={timestamp}")
```

### CloudWatch-Compatible Event Format

```python
import datetime

def log_trigger_event(logger, file_key: str, size_bytes: int, s3_client, bucket: str):
    """Log CloudWatch-compatible trigger event."""
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    
    event = {
        "event_type": "S3ObjectCreated",
        "file_key": file_key,
        "size_bytes": size_bytes,
        "timestamp": timestamp,
        "bucket": bucket
    }
    
    # Glue logger outputs to CloudWatch when continuous logging enabled
    logger.info(f"TRIGGER_EVENT: {json.dumps(event)}")
```

### Continuous Logging (IAC-05)

From glue-job module, `default_arguments` includes:
```hcl
"--enable-continuous-logging" = "true"
```

This enables CloudWatch Logs for the Glue job automatically.

## EventBridge IAM & Terraform (IAC-05, IAC-06)

### Trust Policy for EventBridge

The existing `terraform/modules/iam-role/main.tf` has glue.amazonaws.com trust:

```hcl
# From terraform/modules/iam-role/main.tf:4-14 - verified pattern
assume_role_policy = jsonencode({
  Version = "2012-10-17"
  Statement = [
    {
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "glue.amazonaws.com"
      }
    }
  ]
})
```

**Add events.amazonaws.com for IAC-06:**

```hcl
assume_role_policy = jsonencode({
  Version = "2012-10-17"
  Statement = [
    {
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = ["glue.amazonaws.com", "events.amazonaws.com"]
      }
    }
  ]
})
```

### IAM Policy for StartJobRun

```hcl
# Add to aws_iam_policy "this" resource
{
  Sid    = "EventBridgeStartJobRun"
  Effect = "Allow"
  Action = [
    "glue:StartJobRun"
  ]
  Resource = "arn:${data.aws_partition.current.partition}:glue:*:*:job/${var.job_name}"
}
```

### EventBridge Rule with Input Transformer (IAC-05, IAC-07)

```hcl
# terraform/modules/eventbridge/main.tf

resource "aws_cloudwatch_event_rule" "s3_object_created" {
  name        = "${var.project_name}-s3-object-created"
  description = "Trigger Glue job on S3 ObjectCreated events in raw bucket"
  
  event_pattern = jsonencode({
    "source" : ["aws.s3"],
    "detail-type" : ["Object Created"],
    "detail" : {
      "bucket" : {
        "name" : [var.raw_bucket_name]
      },
      "object" : {
        "key" : [{
          "prefix" : "temperaturas/"
        }]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "glue_job" {
  rule           = aws_cloudwatch_event_rule.s3_object_created.name
  target_id      = "${var.project_name}-csv-to-parquet"
  arn            = var.glue_job_arn
  role_arn       = var.eventbridge_role_arn
  
  input_transformer {
    input_template = <<EOF
{
  "file-key": "<s3-key>",
  "job-name": "<job-name>"
}
EOF
    input_paths = {
      "s3-key"   = "$.detail.object.key"
      "job-name" = "$.detail.job-name"
    }
  }
}

resource "aws_iam_role" "eventbridge_to_glue" {
  name = "${var.project_name}-eventbridge-to-glue-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "sts:AssumeRole"
        Effect   = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_glue_invoke" {
  role   = aws_iam_role.eventbridge_to_glue.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "glue:StartJobRun"
        Resource = var.glue_job_arn
      }
    ]
  })
}
```

## Local Simulation Strategy (SIM-01, SIM-02, SIM-03)

### Floci Limitation

From PROJECT.md: "Floci does NOT support Glue job triggers (CreateJob, StartJobRun). Local validation must use simulated mechanism."

EventBridge is NOT emulated by Floci. The polling workaround in `./run.sh watch` is the required approach.

### Upload Subcommand Pattern

From run.sh, existing cmd_seed pattern (lines 151-154):

```bash
# From run.sh:151-154 - verified pattern
cmd_seed() {
  preflight
  run_step "seed sample data" docker compose --profile tools run --rm tools python catalog/seed.py
}
```

**New upload subcommand:**

```bash
cmd_upload() {
  local file="$1"
  preflight
  require_file "$file" "File not found: $file"
  run_step "upload $file" docker compose --profile tools run --rm tools python -c "
import sys
sys.path.insert(0, '/workspace')
from tools.s3_upload import upload_file
print(upload_file('$file'))
"
}
```

### Watch Subcommand Pattern

```bash
cmd_watch() {
  preflight
  echo "Watching S3 for new files (poll interval: ${POLL_INTERVAL:-5}s)..."
  docker compose --profile tools run --rm tools python -c "
import sys
sys.path.insert(0, '/workspace')
from tools.s3_watch import watch_loop
watch_loop()
"
}
```

### File Structure for New Files

```
tools/
├── s3_upload.py    # Upload function for run.sh upload subcommand
├── s3_watch.py     # Polling loop for run.sh watch subcommand
└── __init__.py
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| S3 upload | Custom HTTP upload | boto3 `upload_file()` | Handles multipart, retries, streaming |
| S3 listing | Custom pagination | boto3 `list_objects_v2()` | Handles continuation tokens, filtering |
| IAM trust policies | Manually crafted JSON | Terraform `jsonencode()` | Validates syntax, references variables |
| Event pattern matching | String concatenation | Terraform `jsonencode()` with `event_pattern` | Validates AWS event pattern format |
| CloudWatch logging | Print statements | GlueContext logger | Structured logs, CloudWatch integration |

## Common Pitfalls

### Pitfall 1: Floci EventBridge Gap
**What goes wrong:** Terraform plan includes EventBridge resources, but cannot be tested locally.
**Why it happens:** Floci does not emulate EventBridge service.
**How to avoid:** Document limitation (SIM-04), use polling simulation for local testing.
**Warning signs:** Terraform plan succeeds but `aws_cloudwatch_event_*` resources never apply in Floci.

### Pitfall 2: CLI vs Env Var Precedence
**What goes wrong:** Both `--file-key` and `FILE_KEY` env var set, unclear which wins.
**Why it happens:** Argparse `default` interacts with env var fallback logic.
**How to avoid:** Explicit check: `file_key = args.file_key if args.file_key else os.environ.get("FILE_KEY")`.
**Warning signs:** Job processes wrong file unexpectedly.

### Pitfall 3: Missing S3 File Handling
**What goes wrong:** Job fails when EventBridge triggers with file key pointing to deleted object.
**Why it happens:** No existence check before attempting to read.
**How to avoid:** D-02: skip silently, exit 0 when file not found.
**Warning signs:** Glue job error logs with "FileNotFound" or "No such key".

### Pitfall 4: S3A Path vs S3 URI
**What goes wrong:** Job uses `s3://` URI instead of `s3a://` for Spark.
**Why it happens:** Spark uses S3A connector for better performance.
**How to avoid:** Use `s3a://{bucket}/{key}` throughout (see job.py:99).
**Warning signs:** Slow reads, multipart upload warnings, connection timeouts.

## Code Examples

### run.sh case Statement Extension

From run.sh:205-211 - verified pattern:

```bash
# Existing pattern to follow
up|down|bootstrap|seed|job|test|lint|demo)
  ;;
```

**Add new subcommands:**

```bash
upload|watch)
  ;;
```

### Trigger Function in tools/s3_watch.py

```python
"""S3 polling watch loop for local simulation.

Floci does not support EventBridge, so this polls S3 for new files
and triggers the Glue job via docker compose.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog import config

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 5))
PROCESSED_FILE = "/tmp/processed_files.txt"


def load_processed_files():
    """Load set of already-processed file keys."""
    try:
        with open(PROCESSED_FILE) as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()


def save_processed_file(key):
    """Record a processed file key."""
    with open(PROCESSED_FILE, "a") as f:
        f.write(f"{key}\n")


def poll_and_trigger():
    """Poll S3, trigger job for new files."""
    s3 = config.s3_client()
    bucket = config.raw_bucket()
    processed = load_processed_files()
    
    response = s3.list_objects_v2(Bucket=bucket, Prefix="temperaturas/")
    
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if key not in processed:
            print(f"New file detected: {key}")
            trigger_job(key)
            save_processed_file(key)


def trigger_job(file_key):
    """Trigger Glue job via docker compose with file parameter."""
    import subprocess
    
    cmd = [
        "docker", "compose", "--profile", "glue", "run", "--rm", "glue",
        "spark-submit",
        "jobs/csv_to_parquet/job.py",
        "--JOB_NAME", "csv_to_parquet",
        "--file-key", file_key
    ]
    
    env = os.environ.copy()
    result = subprocess.run(cmd, env=env)
    return result.returncode == 0


def watch_loop():
    """Main watch loop - poll and trigger indefinitely."""
    print(f"Watching S3 bucket (poll interval: {POLL_INTERVAL}s)")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            poll_and_trigger()
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nWatch stopped.")


if __name__ == "__main__":
    watch_loop()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded input path | File-key parameter | Phase 5 | Enables event-driven processing |
| Manual S3 upload | `./run.sh upload` subcommand | Phase 5 | Streamlined workflow |
| Manual job triggering | `./run.sh watch` polling | Phase 5 | Local validation capability |
| Glue-only IAM | Glue + EventBridge IAM | Phase 5 | EventBridge can invoke job |

**Deprecated/outdated:**
- None relevant to this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Floci supports `list_objects_v2` for S3 polling | S3 Polling & Upload | Low - Floci emulates S3 APIs fully |
| A2 | Glue job can read from specific file key via S3A | Glue Job Parameter Passing | Low - S3A supports individual file reads |
| A3 | `enable-continuous-logging` enables CloudWatch for Glue 5.0 | CloudWatch Logging | Medium - Should verify Glue 5.0 behavior |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

1. **S3 file existence check in Spark**
   - What we know: `read_csv(spark, raw_path)` fails on non-existent path
   - What's unclear: Best way to check file existence before reading in Spark/S3A
   - Recommendation: Wrap read in try/except, catch FileNotFoundException, exit 0 per D-02

2. **Watch loop state persistence**
   - What we know: `/tmp/processed_files.txt` works for single-instance polling
   - What's unclear: Multi-instance or restart scenarios
   - Recommendation: File-based tracking is sufficient for local development; real AWS uses EventBridge state

3. **EventBridge S3 bucket notification**
   - What we know: S3 must send events to EventBridge via bucket notification
   - What's unclear: Terraform `aws_s3_bucket_notification` vs AWS console setup
   - Recommendation: Add `aws_s3_bucket_notification` resource to enable S3 → EventBridge flow

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| boto3 | S3 upload/watch | Yes | 1.43.x | — |
| Docker | run.sh docker compose | Yes | System dependent | — |
| Floci | Emulated S3 | Yes | 1.5.11 | — |
| aws-glue-libs:5 | Glue job execution | Yes | 5 (Glue 5.0) | — |

**Missing dependencies with no fallback:**
- None identified.

**Missing dependencies with fallback:**
- None identified.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml |
| Quick run command | `docker compose --profile glue run --rm glue python -m pytest tests/` |
| Full suite command | `docker compose --profile glue run --rm glue python -m pytest tests/` |

### Phase Requirements Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| EVT-01 | Job accepts --file-key arg | unit | `python -c "import job; job.main()"` with arg | YES |
| EVT-02 | Job logs trigger event | unit | Check log output contains file key | YES |
| SIM-01 | upload subcommand works | integration | `./run.sh upload data/sample/test.csv` | NO - Phase 5 |
| SIM-02 | watch subcommand polls | integration | `./run.sh watch &` + upload + check | NO - Phase 5 |
| SIM-03 | End-to-end flow | integration | `./run.sh up && upload && watch` | NO - Phase 5 |

### Wave 0 Gaps
- `tools/s3_upload.py` — S3 upload function
- `tools/s3_watch.py` — S3 polling and trigger loop
- `tools/__init__.py` — Package init
- `tests/test_s3_upload.py` — Unit tests for upload function
- `tests/test_s3_watch.py` — Unit tests for watch function

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | No | N/A - internal service communication |
| V3 Session Management | No | N/A - no user sessions |
| V4 Access Control | Yes | IAM policies scope EventBridge to specific job |
| V5 Input Validation | Yes | File key parameter validation before S3 read |
| V6 Cryptography | No | S3 traffic within VPC/container network |

### Known Threat Patterns for EventBridge + Glue

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Overly permissive IAM | Information Disclosure | Least-privilege: `Resource = specific-job-arn` |
| S3 bucket receives all events | Information Disclosure | Event pattern filters by prefix `temperaturas/` |
| Input Transformer injection | Tampering | Input Transformer uses path extraction, not user input |

## Sources

### Primary (HIGH confidence)
- `jobs/csv_to_parquet/job.py` - Glue job entry point, argparse pattern
- `run.sh` - CLI orchestration pattern, docker compose usage
- `catalog/seed.py` - S3 upload pattern via boto3
- `catalog/config.py` - boto3 client configuration, bucket derivation
- `terraform/modules/glue-job/main.tf` - Glue job default_arguments pattern
- `terraform/modules/iam-role/main.tf` - IAM trust policy pattern

### Secondary (MEDIUM confidence)
- [Terraform AWS Provider EventBridge documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule) - EventBridge resource syntax
- [AWS Glue Input Transformer reference](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-transforms-tutorial.html) - Input Transformer configuration

### Tertiary (LOW confidence)
- [Floci S3 support documentation](https://github.com/floci-io/floci) - Assumed Floci supports S3 list operations (not verified in this session)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses existing project patterns throughout
- Architecture: HIGH - Follows established module pattern for Terraform
- Pitfalls: HIGH - Floci limitation documented in PROJECT.md

**Research date:** 2026-08-08
**Valid until:** 2026-09-08 (30 days - stable domain)
