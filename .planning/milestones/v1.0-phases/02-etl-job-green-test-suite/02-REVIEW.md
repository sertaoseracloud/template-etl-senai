# Phase 02 - Code Review Report

Phase: 02-etl-job-green-test-suite
Review depth: standard
Files reviewed: 16
Findings: 2 critical, 3 warning, 1 info

---

## Critical Issues

### [CRITICAL] D-08 enforcement test is broken by a missing MULTILINE flag

**File:** `tests/conftest.py:54`
**Claim:** `test_no_aws_sdk_imports` uses `re.search(rf"^import {module}|...")` to find prohibited imports in `transforms/` and `tests/unit/`.
**Problem:** `re.MULTILINE` is never passed to `re.search`. In Python, `^` only matches at the start of the *string* (position 0), not at the start of each line. An import statement anywhere except the very first line of a file will not be matched. This means the test provides a false sense of security: it will pass even when prohibited imports exist deep inside a file.
**Fix:**
```python
if re.search(rf"^import {module}|^from {module}", content, re.MULTILINE):
```

---

### [CRITICAL] Silent S3 error swallowing masks real failures in `athena_query`

**File:** `tests/integration/test_job.py:138-141`
**Claim:** The `head_object` / `put_object` block ensures the Athena output prefix exists before running a query.
**Problem:** If `head_object` raises any `ClientError` (network timeout, permission denied, wrong bucket, etc.), it is silently caught by the bare `except ClientError` and a placeholder object is created with `put_object`. The Athena query then runs against a potentially wrong or inaccessible bucket, returning garbage or failing with an opaque error. The original error context is lost entirely.
**Fix:**
```python
try:
    s3.head_object(Bucket=curated_bucket(), Key=result_key)
except s3.exceptions.ClientError as exc:
    if exc.response["Error"]["Code"] == "404":
        s3.put_object(Bucket=curated_bucket(), Key=result_key, Body=b"")
    else:
        raise  # re-raise permission errors, network errors, etc.
```

---

## Warnings

### [WARNING] Append mode + no atomic committer risks silent data duplication

**File:** `transforms/csv_to_parquet.py:152`
**Claim:** `write_parquet` uses `mode("append")` so multiple job runs accumulate parquet files.
**Problem:** The integration test `test_job_output_content` runs `run_job_subprocess` twice per module session (once in `test_job_runs_successfully`, once in `test_job_output_content`). With append mode and the default FileOutputCommitter, the second run writes 18 additional files on top of the first 18. The assertion `len(parquet_keys) >= 18` passes in both cases, so the test does not detect the accumulation. If a job ever reruns in production with the same partitions, data doubles silently. The content assertion (D-04) is only a safety net if the test is *designed* to catch it — here it is not.
**Fix:** Either assert `len(parquet_keys) == 18` (strict, requires function-scoped fixture), or change `write_parquet` to `mode("overwrite")` and update `test_job_output_content` to have function-scoped cleanup so each test run starts clean.

---

### [WARNING] `env_value` in `run.sh` cannot distinguish "missing variable" from "empty value"

**File:** `run.sh:21`
**Claim:** `env_value` reads a named variable from `.env` and returns its value.
**Problem:** `grep -E "^VAR=" .env` exits 0 (found, possibly empty) or 1 (not found); `|| true` always masks the failure, so the return code is always 0. When a variable is absent from `.env`, `grep` emits nothing, `tail` emits nothing, and `printf '%s' ""` returns an empty string — identical to the case where the variable is present but set to an empty value (`VAR=`). The preflight check works correctly because it explicitly tests `-z "$value"`, but the `env_value` helper itself provides no way to tell the two cases apart.
**Fix:** Let `env_value` return a distinguishable sentinel (e.g., return 1 on not-found so the caller can test `$?`). Alternatively, document that this function cannot distinguish absent from empty and that callers must handle both.

---

### [WARNING] Spark session not stopped on error paths in `job.py`

**File:** `jobs/csv_to_parquet/job.py:84-111`
**Claim:** The Spark session is created and used for the job.
**Problem:** If any exception occurs between `spark = ...getOrCreate()` (line 89) and `job.commit()` (line 111) — for example, a KeyError from a missing env var in `apply_s3a_config`, or an exception from `read_csv` or the transform chain — the Spark session is never stopped. In the Glue container, the JVM process may linger. For a Glue job this is usually acceptable (the container is ephemeral), but it is still a resource leak and makes debugging harder.
**Fix:** Wrap the body of `main()` in a `try/finally`:
```python
spark = SparkSession.builder.appName(args.JOB_NAME).getOrCreate()
try:
    spark, _, _ = apply_s3a_config(spark)
    # ... rest of main
    job.commit()
finally:
    spark.stop()
```

---

## Info

### [INFO] D-04 fixture is module-scoped but some tests accumulate state

**File:** `tests/integration/test_job.py:176-183`
**Issue:** The `clean_curated` fixture is module-scoped, so it runs once before the first integration test. Each subsequent test in the module sees the curated bucket as left by the previous test. While this does not cause any test to fail (all assertions use `>=` or sequential checks), it means `test_job_output_content` and all Athena tests are running against output from the *previous* test's job run, not a fresh run. The state is deterministic (thanks to module-scope cleanup at the start), but the intent of each individual test is obscured.
**Fix:** Add a comment clarifying that module scope is intentional and that each test verifies incremental accumulation, not a single clean run.

---

## Per-File Notes

### `jobs/csv_to_parquet/job.py` — No issues found

The committer rationale block (lines 7-28) accurately describes the three options considered and the decision made. The inline derivation of bucket names from `PROJECT_NAME` (lines 66-67) is consistent with `catalog/config.py`. Environment variables are read directly with `os.environ[]` (no silent defaulting). The empty-output guard on line 105 is appropriate.

### `docker-compose.yml` — No issues found

Privileged mode and `NET_RAW` are required by Floci (documented in comments). The read-only volume mount for the tools container is a good security posture. Health-check dependency ordering is correct.

### `run.sh` — No issues found

`set -euo pipefail` is correctly used. The `env_value` helper avoids sourcing `.env` (T-01-03 mitigation). The `require_file` guard on `cmd_job` prevents a Phase-1 clone from triggering a ~4.8 GB Glue image pull. The real-AWS endpoint guard on line 96-99 is sound.

### `docs/LOCAL_DEV.md` — Minor documentation inconsistency

The table marks `FLOCI_HOST_PORT` as **Required: Yes**, but the description and the `docker-compose.yml` default (`${FLOCI_HOST_PORT:-4566}`) show it has a default. Should be **Required: No**.

### `tests/__init__.py`, `tests/unit/__init__.py` — No issues (empty package markers)

### `tests/integration/__init__.py` — No issues (empty file)

### `tests/unit/test_transforms.py` — No issues found

Good test coverage: identity/accumulation tests for `derive_temp_media`, non-mutation assertions for both `add_city_key` and `derive_temp_media`, parametrized city-key normalization, and an end-to-end round-trip for `write_parquet`. Note that `test_normalize_city_key_florianopolis` (line 43) is a strict duplicate of the parametrized `test_normalize_city_key_all_six_cities` (line 38) — dead weight but not a bug.

### `transforms/__init__.py` — No issues found

Clean re-exports with correct `__all__`.

### `transforms/csv_to_parquet.py` — No issues found

The committer rationale block is byte-for-byte identical to the one in `job.py`; both accurately describe the default FileOutputCommitter behavior. D-08 compliance is correctly enforced (only `pyspark.sql` and stdlib imports). The UDF registered at module level (line 73) is idiomatic and safe.

### `catalog/__init__.py` — No issues (empty package marker)

### `catalog/bootstrap.py` — No issues found

Idempotency strategy is sound: `AlreadyExistsException` is caught and handled separately from other `ClientError`s. The Floci `InvalidAction` distinction is correctly documented and implemented. `strict=True` in `zip()` on line 227 guards against mismatched partition key/value lengths. `validate_schema` uses safe `.get()` calls throughout.

### `catalog/seed.py` — No issues found

`upload_samples` raises `FileNotFoundError` on an empty upload (line 59), which is the correct behavior — not a silent success. The `ensure_bucket` function correctly handles `BucketAlreadyOwnedByYou` alongside `BucketAlreadyExists`.

### `catalog/config.py` — No issues found

The single-derivation-site design (bucket names and database name from `PROJECT_NAME`) is correct and well-documented. The `endpoint_url` guard (lines 71-74) prevents the real-AWS fallback accident (T-01-03). The `s3_client()` and `glue_client()` functions return new client instances on each call, which is the correct pattern for boto3.

---

_Reviewed: 2026-08-08T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
