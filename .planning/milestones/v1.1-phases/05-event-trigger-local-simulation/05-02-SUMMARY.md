---
phase: "05"
plan: "02"
subsystem: terraform
tags: [eventbridge, aws, infrastructure, s3-trigger, glue]
dependency_graph:
  requires:
    - module: glue-job
      reason: "EventBridge invokes Glue job via StartJobRun"
  provides:
    - module: eventbridge
      reason: "S3 ObjectCreated -> EventBridge -> Glue pipeline"
  affects:
    - module: s3-buckets
      reason: "Adds EventBridge notification configuration to raw bucket"
tech_stack:
  added: [terraform, aws_eventbridge, aws_cloudwatch, aws_iam_role]
  patterns: [event-driven-architecture, input-transformer, cloudtrail-integration]
key_files:
  created:
    - terraform/modules/eventbridge/main.tf
    - terraform/modules/eventbridge/variables.tf
    - terraform/modules/eventbridge/outputs.tf
  modified:
    - terraform/main.tf
    - terraform/modules/glue-job/main.tf
    - terraform/modules/glue-job/variables.tf
decisions:
  - id: "05-02-01"
    decision: "Use CloudTrail-based event pattern for S3 ObjectCreated detection"
    rationale: "S3 ObjectCreated events arrive via CloudTrail, not direct EventBridge events. Required eventName filters for PutObject/CompleteMultipartUpload."
  - id: "05-02-02"
    decision: "Use Input Transformer with comma-separated format for StartJobRun"
    rationale: "StartJobRun API expects job arguments as comma-separated '--param', 'value' format, not JSON."
  - id: "05-02-03"
    decision: "Create dedicated IAM role for EventBridge->Glue invocation"
    rationale: "Least privilege - EventBridge service assumes role with only StartJobRun/GetJobRun on specific job ARN."
metrics:
  duration: "execution-time"
  tasks: 3
  commits: 2
  files_created: 3
  files_modified: 3
status: complete
actuals:
  tokens: 22000
  tasks: 3
  commits: 2
---

# Phase 5 Plan 2: Terraform EventBridge Infrastructure Summary

## Goal Achieved

Provisioned EventBridge infrastructure via Terraform: S3 ObjectCreated event rule, IAM role allowing EventBridge to invoke Glue, and Input Transformer passing S3 key as job parameter.

## Tasks Completed

### Task 1: EventBridge Module (Tracer) - COMPLETED

**Created files:**
- `terraform/modules/eventbridge/main.tf` - EventBridge rule, IAM role, event target, S3 notification
- `terraform/modules/eventbridge/variables.tf` - project_name, raw_bucket_name, glue_job_arn, prefix
- `terraform/modules/eventbridge/outputs.tf` - exports eventbridge_role_arn

**Key components:**
- `aws_cloudwatch_event_rule.s3_object_created` - CloudTrail-based S3 event pattern
- `aws_iam_role.eventbridge_to_glue` - Trust policy for events.amazonaws.com
- `aws_iam_role_policy.eventbridge_glue_invoke` - StartJobRun permission on specific job
- `aws_cloudwatch_event_target.glue_job` - Input Transformer with `--file-key` parameter
- `aws_s3_bucket_notification.to_eventbridge` - S3 -> EventBridge event delivery

**Commit:** `a3130da` - feat(terraform): add EventBridge module for S3 ObjectCreated trigger

### Task 2: Update Glue-Job Module - COMPLETED

**Modified files:**
- `terraform/modules/glue-job/variables.tf` - Added `default_file_key` and `default_arguments` variables
- `terraform/modules/glue-job/main.tf` - Merged `--file-key` into default_arguments map

**Commit:** `1dee8e0` - feat(terraform): add --file-key parameter to glue-job module

### Task 3: Wire EventBridge Module - COMPLETED

**Modified files:**
- `terraform/main.tf` - Added `module "eventbridge"` block connecting to glue-job module

## Success Criteria Verification

| Criterion | Status |
|-----------|--------|
| terraform/modules/eventbridge/main.tf exists with EventBridge rule | PASS |
| terraform/modules/eventbridge/variables.tf defines required variables | PASS |
| terraform/modules/eventbridge/outputs.tf exports eventbridge_role_arn | PASS |
| terraform/main.tf includes eventbridge module | PASS |
| IAM role has events.amazonaws.com trust policy | PASS |
| Input Transformer passes S3 key as --file-key parameter | PASS |

## Threat Mitigations Applied

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-05-04 | Event pattern filters by eventName and bucket name | Applied |
| T-05-05 | IAM policy restricts to specific job ARN only (least privilege) | Applied |
| T-05-06 | Input Transformer extracts from CloudTrail structure | Accepted |
| T-05-07 | Event pattern only extracts key path | Accepted |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Notes

Terraform fmt and validate commands were not executed because `terraform` CLI is not available in this environment. Manual verification required:

```bash
cd terraform && terraform fmt -check -recursive && terraform validate
```

## Requirements Completed

- IAC-05: EventBridge rule for S3 ObjectCreated via CloudTrail
- IAC-06: IAM role allowing EventBridge to invoke Glue job
- IAC-07: Input Transformer passing S3 key as job parameter

## Self-Check: PASSED

All required files created and modified. Commits verified in git history.
