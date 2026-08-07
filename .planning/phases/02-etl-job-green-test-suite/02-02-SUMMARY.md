---
phase: "02-etl-job-green-test-suite"
plan: "02"
subsystem: "jobs/csv_to_parquet"
tags: [pyspark, awsglue, s3a, etl, job, glue-context]
dependency_graph:
  requires: ["02-01"]
  provides: [JOB-01, JOB-02, JOB-03, JOB-04, JOB-05]
  affects: [run.sh, tests/integration/]
tech_stack:
  added: [awsglue, argparse]
  patterns: [thin-entrypoint, glue-context-wiring, s3a-config-from-env, compound-partitioning, empty-output-guard, committer-rationale-block]
key_files:
  created:
    - jobs/__init__.py
    - jobs/csv_to_parquet/__init__.py
    - jobs/csv_to_parquet/job.py
decisions:
  - id: D-05
    text: "S3A config block lives in job code, applied as one unit via apply_s3a_config(spark), reading from os.environ directly — NOT from catalog.config (which imports boto3) and NOT from spark-submit arguments."
  - id: D-09
    text: "Job reads the full s3a:// prefix (3 CSVs, 18 rows total) — NOT input.csv or any individual file."
  - id: D-10
    text: "Job explicitly fails with sys.exit message when output DataFrame is empty, instead of exiting 0 silently."
  - id: D-11
    text: "Demo summary prints concrete numbers: rows_read, output_rows, partitions (18), s3a input path, s3a output path."
  - id: D-12
    text: "Compound partitioning by data_medicao + cidade_key = 3 dates x 6 cities = 18 partitions (supersedes D-17 of Phase 1)."
  - id: D-13
    text: "cidade_key normalized (lowercase, no accents via NFKD); cidade column preserved."
  - id: committer-decision
    text: "Default FileOutputCommitter used — committer rationale block documented verbatim from RESEARCH.md at top of job.py. Magic committer rejected (Floci Issue #30 GetObjectAttributes gap); directory staging rejected (zero benefit at 18 KB scale)."
metrics:
  tasks: 3
  commits: 4
  files: 4
status: partial
---

# Phase 02 Plan 02: ETL Job Entry Point Summary

ETL job entry point that wires argparse, GlueContext, the S3A configuration block, and the transforms module together. End-to-end verification blocked by missing environment.

## What Was Built

**`jobs/csv_to_parquet/job.py`** — The only file in the project that imports `awsglue`. All transformation logic stays in `transforms/`.

Key features:
- `argparse` for `--JOB_NAME` (Glue entrypoint convention)
- `SparkSession.builder.appName(...).getOrCreate()` then `GlueContext(spark.sparkContext)`
- `Job(glue_context)` with `job.init(args.JOB_NAME, args)` / `job.commit()`
- `apply_s3a_config(spark)` — applies the complete S3A config block as one unit, reading exclusively from `os.environ`:
  - `fs.s3a.endpoint`, `fs.s3a.path.style.access`, `fs.s3a.connection.ssl.enabled`
  - `fs.s3a.aws.credentials.provider` = `SimpleAWSCredentialsProvider`
  - `fs.s3a.access.key`, `fs.s3a.secret.key`, `fs.s3a.endpoint.region`
- Bucket names derived inline from `PROJECT_NAME` (same `.replace('_', '-')` logic as `catalog/config.py`) to avoid importing boto3
- Reads full prefix `s3a://${project}-raw/temperaturas/` (3 CSVs, 18 rows)
- `add_city_key` then `derive_temp_media` transforms
- Empty-output guard: `sys.exit("Job output is empty. Aborting...")`
- `write_parquet(..., partition_cols=["data_medicao", "cidade_key"])` — compound, 18 partitions
- Demo summary with concrete numbers after `job.commit()`
- Committer rationale block at top of file (RESEARCH.md verbatim)

**`jobs/__init__.py`** and **`jobs/csv_to_parquet/__init__.py`** — empty package markers.

## Decisions Made

### D-05: S3A config from os.environ, not catalog.config
`catalog/config.py` imports `boto3`, which is forbidden in the job context (D-08). The bucket derivation logic is reproduced inline in `apply_s3a_config` with a comment noting that if the derivation ever changes, both files must be kept in sync.

### D-09: Full prefix read, not individual file
Path is `s3a://.../temperaturas/` — Spark reads all files matching that prefix. No `input.csv` or any specific file is named.

### D-10: Explicit empty-output failure
`sys.exit("Job output is empty. Aborting -- check input data at: " + raw_path)` instead of a silent 0 exit.

### D-11: Demo summary with concrete numbers
Prints: rows_read, output_rows, partitions (18), s3a input path, s3a output path.

### D-12/D-13: Compound partitioning
`data_medicao + cidade_key` = 3 dates x 6 cities = 18 Hive-style partitions. `cidade_key` is NFKD-normalized (lowercase, no accents); `cidade` column is preserved.

### Committer decision
Default FileOutputCommitter. Magic rejected (Floci Issue #30); directory staging rejected (zero benefit at 18 KB scale). Rationale block at top of job.py per RESEARCH.md.

## Commits

| Hash | Message |
|------|---------|
| `233d836` | feat(02-02): ETL job entry point -- GlueContext wiring, S3A config, transforms |
| `b7a7db8` | fix(02-02): correct return type annotation of apply_s3a_config |
| `a4d8c3f` | docs(02-02): confirm run.sh guards -- no changes needed |

## Deviations from Plan

### Rule 1 - Bug Fix: Return type annotation
**Found during:** Task 1 post-commit verification
**Issue:** `apply_s3a_config` was annotated `-> SparkSession` but returned `tuple[SparkSession, str, str]`.
**Fix:** Corrected annotation to `-> tuple[SparkSession, str, str]`.
**Commit:** `b7a7db8`

### Task 3 Blocked: Environment precondition unmet
**Blocked by:** `./run.sh up` precondition failed — `.env` absent from disk (not committed, not in `.gitignore`), Docker containers not running, Python not installed on host.
**Impact:** Tasks 1 and 2 fully committed. Task 3 (end-to-end job verification inside Docker) cannot be executed by this agent.
**Resolution:** Operator must create `.env` from `.env.example`, ensure Docker is running, then run `./run.sh up`. Agent can resume from Task 3 afterward.

## Requirements Covered

| Requirement | Status | Evidence |
|---|---|---|
| JOB-01 (read CSV, write Parquet) | Code committed | `read_csv` / `write_parquet` wired in job.py; end-to-end verification pending Task 3 |
| JOB-02 (thin entrypoint + pure transforms) | Done | `jobs/csv_to_parquet/job.py` imports from `transforms/` only; awsglue isolated here |
| JOB-03 (explicit s3a:// via from_options) | Done | `s3a://` paths constructed and passed to transforms; no from_catalog anywhere |
| JOB-04 (S3A block as one unit) | Done | `apply_s3a_config(spark)` applies all 7 Hadoop config calls atomically |
| JOB-05 (same code for real AWS) | Done | No literals; all config from `os.environ` — swap env vars to point at real AWS |

## D-08 Compliance

`jobs/csv_to_parquet/job.py` contains zero `import boto3`, `from boto3`, `import catalog`, or `from catalog`. The string `catalog.config` appears only in comments explaining why it is NOT imported. The `transforms/` module is untouched by this plan (already compliant from 02-01).

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: credential-env | jobs/csv_to_parquet/job.py | Reads AWS_ACCESS_KEY_ID/SECRET from os.environ — no credential literals in source. Accepted risk (T-02-01): test-dummy values from .env only, no real credentials exist in this project. |
| threat_flag: bucket-derivation-sync | jobs/csv_to_parquet/job.py | Inline bucket derivation must stay in sync with catalog/config.py. Documented in code comment (T-02-02). |

## Self-Check

All committed files confirmed present:

```
jobs/__init__.py                  FOUND
jobs/csv_to_parquet/__init__.py   FOUND
jobs/csv_to_parquet/job.py        FOUND
```

All commit hashes confirmed in git log:

```
233d836 feat(02-02): ETL job entry point
b7a7db8 fix(02-02): correct return type annotation
a4d8c3f docs(02-02): confirm run.sh guards
```

Manual verification results (no Python/Docker on host):

| Check | Result |
|---|---|
| No `import boto3` / `from boto3` in job.py | PASS (grep confirmed) |
| No `import catalog` / `from catalog` in job.py | PASS (grep confirmed) |
| `awsglue` imported (GlueContext + Job) | PASS (grep confirmed) |
| `s3a://` paths present (4 lines: 2 paths + 2 print) | PASS (grep confirmed) |
| `sys.exit` empty-output guard present | PASS (code review confirmed) |
| `job.commit()` present | PASS (code review confirmed) |
| `partition_cols=["data_medicao", "cidade_key"]` | PASS (code review confirmed) |
| Committer rationale block at top of file | PASS (code review confirmed) |
| `run.sh` cmd_job guard: `require_file jobs/csv_to_parquet/job.py` | PASS (grep confirmed) |
| `run.sh` cmd_test guard: `require_file tests` | PASS (grep confirmed) |
| No endpoint/bucket/credential literals in run.sh | PASS (preflight uses env vars from .env only) |

## Plan Status

**Tasks completed:** 2/3 (Tasks 1 and 2 fully committed; Task 3 blocked)

**Task 3 is not deferred — it is the next action.** The agent should resume with `./run.sh up` once the operator has set up the environment.

## Self-Check: PASSED (with Task 3 pending environment setup)
