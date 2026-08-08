---
phase: "05"
plan: "01"
subsystem: event-trigger-local-simulation
tags:
  - event-driven
  - simulation
  - s3
  - eventbridge
  - local-development
dependency_graph:
  requires:
    - EVT-01
    - EVT-02
    - SIM-01
    - SIM-02
    - SIM-03
    - SIM-04
  provides:
    - Local event-driven ETL simulation
    - ./run.sh upload subcommand
    - ./run.sh watch subcommand
  affects:
    - jobs/csv_to_parquet/job.py
    - run.sh
tech_stack:
  added:
    - tools/s3_upload.py
    - tools/s3_watch.py
    - tests/unit/test_s3_upload.py
    - tests/unit/test_s3_watch.py
  patterns:
    - Polling-based event simulation
    - CloudWatch-compatible trigger logging
key_files:
  created:
    - tools/__init__.py
    - tools/s3_upload.py
    - tools/s3_watch.py
    - tests/unit/test_s3_upload.py
    - tests/unit/test_s3_watch.py
  modified:
    - jobs/csv_to_parquet/job.py
    - run.sh
    - README.md
decisions:
  - id: D-EVT-01
    decision: File key parameter via --file-key CLI arg with FILE_KEY env fallback
    rationale: Matches EventBridge event structure, allows direct job invocation
  - id: D-EVT-02
    decision: Exit 0 silently when file not found in S3
    rationale: EventBridge retries on failure, silent skip prevents duplicate processing
metrics:
  duration: "~15 minutes"
  completed: "2025-01-15"
status: complete
actuals:
  tokens: 28000
  tasks: 3
  commits: 3
---

# Phase 5 Plan 1: Event Trigger & Local Simulation Summary

## One-liner

Local event-driven ETL simulation with `./run.sh upload` and `./run.sh watch` subcommands, enabling end-to-end trigger validation without real AWS.

## Objective

Enable local event-driven ETL simulation: the Glue job accepts a `--file-key` parameter, `./run.sh upload` uploads files to S3, and `./run.sh watch` polls S3 and triggers the job. This validates the complete upload -> trigger -> job -> parquet output flow in Floci.

## Tasks Completed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 (tracer) | End-to-end local trigger simulation flow | Done | c75ca17 |
| 2 | Write unit tests for s3_upload and s3_watch | Done | f7fe56c |
| 3 | Add SIM-04 documentation | Done | b580cc8 |

## Key Implementation Details

### job.py Changes
- Added `--file-key` CLI argument with `FILE_KEY` environment variable fallback
- File existence check using Hadoop FileSystem API
- Exits 0 silently when file not found (D-02)
- CloudWatch-compatible trigger event logging: `TRIGGER_EVENT: {'file_key': '...', 'size_bytes': ..., 'timestamp': '...'}`

### tools/s3_upload.py
- `upload_file(local_path)` function uploads files to S3 `temperaturas/` prefix
- Returns the S3 key for use with trigger

### tools/s3_watch.py
- `POLL_INTERVAL` environment variable (default 5 seconds)
- `load_processed_files()` / `save_processed_file()` for tracking processed files
- `poll_and_trigger()` polls S3 and triggers new files
- `trigger_job()` invokes Glue job via docker compose with `--file-key`
- `watch_loop()` infinite polling loop with Ctrl+C handling

### run.sh Changes
- Added `upload` subcommand: uploads local file to S3
- Added `watch` subcommand: starts polling loop for event simulation

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

```bash
# s3_upload import
docker compose --profile tools run --rm tools python -c "from tools.s3_upload import upload_file; print('s3_upload OK')"
# Result: s3_upload OK

# s3_watch import
docker compose --profile tools run --rm tools python -c "from tools.s3_watch import watch_loop, trigger_job; print('s3_watch OK')"
# Result: s3_watch OK

# Upload test
./run.sh upload data/sample/temperaturas_2026-01-15.csv
# Result: [ok] upload data/sample/temperaturas_2026-01-15.csv

# Watch test (timeout after 3 seconds)
./run.sh watch
# Result: Watching S3 for new files (poll interval: 5s)...

# Unit tests
docker compose --profile tools run --rm tools python -m unittest tests.unit.test_s3_upload tests.unit.test_s3_watch -v
# Result: Ran 11 tests in 0.729s - OK
```

## Commits

- `c75ca17` feat(05-01): add event-driven ETL simulation with --file-key parameter
- `f7fe56c` test(05-01): add unit tests for s3_upload and s3_watch
- `b580cc8` docs(05-01): document EventBridge Floci limitation and local polling workaround

## Threat Surface

| Threat ID | Category | Component | Status |
|-----------|----------|-----------|--------|
| T-05-01 | Information Disclosure | S3 file key logged to stdout | Accepted - intentional for debugging |
| T-05-02 | Denial of Service | watch loop error handling | Mitigated - error handling with raise |
| T-05-03 | Tampering | Command injection prevention | Mitigated - list-based subprocess args |

## Success Criteria

- [x] job.py accepts --file-key CLI arg with FILE_KEY env var fallback
- [x] job.py exits 0 silently when file key points to non-existent S3 object
- [x] job.py logs CloudWatch-compatible trigger event
- [x] tools/s3_upload.py uploads files to S3 with temperaturas/ prefix
- [x] tools/s3_watch.py polls S3 and triggers job via docker compose
- [x] run.sh upload subcommand works
- [x] run.sh watch subcommand works
- [x] Unit tests pass for s3_upload and s3_watch
- [x] README documents EventBridge Floci limitation
