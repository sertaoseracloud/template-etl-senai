---
phase: "06"
plan: "01"
subsystem: "performance-testing"
tags: ["performance", "testing", "etl", "benchmark"]
key_files:
  - "scripts/generate_test_data.py"
  - "tests/unit/test_generate_test_data.py"
  - "tests/integration/test_perf_test.py"
  - "run.sh"
  - "terraform/modules/eventbridge/VALIDATION.md"
tech_stack:
  added: ["csv stdlib", "argparse", "unittest"]
  patterns: ["performance testing", "throughput measurement", "structured JSON logging"]
dependency_graph:
  requires: []
  provides: ["PERF-01", "PERF-02", "PERF-03", "PERF-04", "PERF-05", "EVT-03", "EVT-04", "EVT-05"]
  affects: ["transforms/csv_to_parquet.py", "jobs/csv_to_parquet/job.py"]
decisions:
  - "normalize_key() implemented to exactly match transforms.normalize_city_key() using NFKD normalization"
  - "CSV generation uses csv.writer (stdlib only, no pandas) per D-08 invariant"
  - "Performance results written as JSON to results/perf-TIMESTAMP.json"
  - "EventBridge Input Transformer documented with JSONPath expressions"
metrics:
  duration: "N/A"
  tasks_completed: 3
  commits: 3
status: "complete"
actuals:
  tokens: 0
  tasks: 3
  commits: 3
---

# Phase 6 Plan 1: Performance Testing Infrastructure Summary

## One-liner

Dynamic test data generator creates configurable datasets, performance tests measure throughput and log structured JSON results.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | End-to-end performance test flow (tracer) | a4faee3 | scripts/generate_test_data.py, run.sh, tests/integration/test_perf_test.py |
| 2 | Unit tests for generate_test_data.py | 44f8639 | tests/unit/test_generate_test_data.py |
| 3 | Phase 5 EventBridge documentation validation | fb7ef24 | terraform/modules/eventbridge/VALIDATION.md |

## What Was Built

### scripts/generate_test_data.py

- CLI with `--rows N` (required), `--output PATH` (required), `--date YYYY-MM-DD` (default: 2026-01-15)
- Generates CSV with columns: cidade, cidade_key, data_medicao, temp_min, temp_max
- Uses 6 SC-Brazil cities: Florianopolis, Joinville, Blumenau, Chapeco, Lages, Criciuma
- `normalize_key()` matches transforms.csv_to_parquet.normalize_city_key() exactly (NFKD normalization)
- temp_min: 10.0-25.0, temp_max: 20.0-35.0 (always >= temp_min)
- Uses csv.writer (stdlib only, no pandas)

### run.sh

- Added `perf-test` subcommand to case statement
- `cmd_perf_test()` function:
  - Takes n_rows as positional argument
  - Generates temp CSV via generate_test_data.py
  - Uploads via s3_upload.upload_file()
  - Runs job.py with --file-key pointing to uploaded file
  - Measures end-to-end timing with time measurement
  - Logs structured JSON to results/perf-TIMESTAMP.json

### tests/unit/test_generate_test_data.py

12 unit tests (all passing):
- test_cli_rows_output
- test_cli_invalid_rows
- test_cli_invalid_date
- test_schema_compliance
- test_date_format
- test_temp_range
- test_temp_max_gte_min
- test_row_has_required_fields
- test_normalize_key_matches_transforms
- test_normalize_key_lowercases
- test_normalize_key_removes_accents
- test_json_format

### tests/integration/test_perf_test.py

Integration tests validating:
- generate_test_data.py produces correct CSV structure
- perf-test subcommand is recognized
- JSON result schema is documented
- normalize_key consistency with transforms

### terraform/modules/eventbridge/VALIDATION.md

Documentation covering:
- How to test EventBridge locally via `./run.sh watch`
- How EventBridge would trigger in real AWS (CloudTrail event pattern)
- Input Transformer JSONPath expressions explained
- IAM policy for Glue job invocation
- Validation checklist for EVT-03, EVT-04, EVT-05

## Deviations from Plan

None - plan executed exactly as written.

## Verification

```bash
# Generate test data
python scripts/generate_test_data.py --rows 100 --output /tmp/test.csv
# Output: Generated 100 rows -> /tmp/test.csv

# Run unit tests
python -m unittest tests.unit.test_generate_test_data -v
# Output: Ran 12 tests in 1.780s - OK

# Verify EventBridge infrastructure
grep -l "aws_cloudwatch_event_rule" terraform/modules/eventbridge/main.tf
grep -l "input_transformer" terraform/modules/eventbridge/main.tf
```

## Requirements Coverage

| ID | Requirement | Status |
|----|-------------|--------|
| PERF-01 | Script generates CSV with configurable number of rows | Done |
| PERF-02 | Supports --rows, --output, --date matching schema | Done |
| PERF-03 | ./run.sh perf-test N runs full pipeline | Done |
| PERF-04 | Logs execution time and throughput (rows/second) | Done |
| PERF-05 | Results in structured JSON format | Done |
| EVT-03 | EventBridge rule targets Glue job | Documented |
| EVT-04 | Input Transformer extracts S3 key | Documented |
| EVT-05 | IAM policy restricts to specific job | Documented |

## Self-Check: PASSED

- scripts/generate_test_data.py: FOUND
- tests/unit/test_generate_test_data.py: FOUND (12 tests passing)
- tests/integration/test_perf_test.py: FOUND
- terraform/modules/eventbridge/VALIDATION.md: FOUND
- Commits a4faee3, 44f8639, fb7ef24: FOUND
