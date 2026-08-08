# Phase 5: Event Trigger & Local Simulation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-08
**Phase:** 05-Event Trigger & Local Simulation
**Areas discussed:** File Key Reception, Upload Mechanism, File Detection (watch), EventBridge Provisioning

---

## File Key Reception

| Option | Description | Selected |
|--------|-------------|----------|
| CLI arg | Pass `--file-key <key>` as a command-line argument. Job already uses argparse — simple addition. | |
| Environment variable | Read `FILE_KEY` from environment variable. Job already reads from os.environ for AWS config. | |
| Both (arg + env) | Use both: CLI arg with env var as fallback. More flexible but adds complexity. | ✓ |

**User's choice:** Both (arg + env) — CLI arg takes priority, env var is fallback
**Notes:** Non-existent file key → skip silently and exit 0

---

## Upload Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Use existing tools service | Add run_step using tools service with boto3. Leverages existing tools service. | ✓ |
| New Python script | Add a separate script in `scripts/upload.py` that handles boto3 upload directly. | |
| awscli cp command | Use `aws s3 cp` CLI inside the tools container. Simple but requires awscli package. | |

**User's choice:** Use existing tools service
**Notes:** S3 key printed to stdout after upload

---

## File Detection (watch)

| Option | Description | Selected |
|--------|-------------|----------|
| Polling | Run a background `watch` subcommand that polls S3 with boto3 list_objects_v2 every N seconds and triggers job. Simple, reliable. | ✓ |
| ListObjectsV2 polling | Use S3 ListObjectsV2 via a watch subcommand, similar to polling but with timestamp-based filtering. | |
| Direct trigger only | Simpler version that takes a file path directly: `./run.sh trigger <s3-key>`. No polling, user controls timing. | |

**User's choice:** Polling
**Notes:** 5 seconds polling interval (configurable via POLL_INTERVAL env var)

---

## EventBridge Provisioning

| Option | Description | Selected |
|--------|-------------|----------|
| S3 EventBridge integration | Add EventBridge data source block pointing to the existing raw bucket, filtered for ObjectCreated events. | ✓ |
| EventBridge + SQS | Add EventBridge with S3 Event pattern + separate SQS queue for durability. More complex but decouples trigger from job. | |
| Glue Trigger only | Skip EventBridge for now, only add the Glue job trigger resource in Terraform. Simpler but less complete. | |

**User's choice:** S3 EventBridge integration
**Notes:** Job logs trigger events to CloudWatch Logs

---

## Claude's Discretion

No areas deferred to Claude's discretion — all decisions made by user.

## Deferred Ideas

None — all ideas discussed were within Phase 5 scope.
