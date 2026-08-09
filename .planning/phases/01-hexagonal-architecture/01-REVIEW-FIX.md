---
phase: "01"
fixed_at: "2026-08-09T00:00:00Z"
review_path: ".planning/phases/01-hexagonal-architecture/01-REVIEW.md"
iteration: 1
findings_in_scope: 8
fixed: 7
skipped: 1
status: partial
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-08-09T00:00:00Z
**Source review:** .planning/phases/01-hexagonal-architecture/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8
- Fixed: 7
- Skipped: 1

## Fixed Issues

### CR-01: Silent exception swallowing masks failures

**Files modified:** `jobs/csv_to_parquet/adapters/secondary/spark_adapter.py`
**Commit:** 070d6b2
**Applied fix:** Added `logging.warning()` when `get_file_info` catches an exception, replacing the silent `pass` block.

### CR-02: Empty except clause with no handling

**Files modified:** `jobs/csv_to_parquet/application/use_cases.py`
**Commit:** 80b3c2f
**Applied fix:** Moved `input_path = ""` initialization before the try block. Removed fragile `locals()` workaround from exception handlers. FileNotFoundError handler is now reachable.

### CR-03: data_key always reports 0

**Files modified:** `jobs/csv_to_parquet/adapters/primary/glue_adapter.py`
**Commit:** fcc3efb
**Applied fix:** Changed hardcoded `0` to `result.file_size_bytes` in CloudWatch log event.

### WR-01: Output path always batch "temperaturas/" for single file processing

**Files modified:** `jobs/csv_to_parquet/application/use_cases.py`
**Commit:** 80b3c2f
**Applied fix:** Added conditional logic to append `file_key.rsplit('.', 1)[0]` to output path when processing single files in event-driven mode.

### WR-02: Unused local variable with fragile workaround

**Files modified:** `jobs/csv_to_parquet/application/use_cases.py`
**Commit:** 80b3c2f
**Applied fix:** Initialized `input_path` before try block eliminates need for `locals()` workaround.

### WR-04: No validation that partition columns exist

**Files modified:** `jobs/csv_to_parquet/application/dto.py`
**Commit:** 1bca45b
**Applied fix:** Added validation in `JobRequest.__post_init__` to ensure `partition_cols` is not empty.

### WR-05: Job.init() called after execution

**Files modified:** `jobs/csv_to_parquet/job.py`
**Commit:** 082b66c
**Applied fix:** Moved `Job(...).init()` call to before `adapter.run()`, restoring correct Glue execution order: init() -> do work -> commit().

## Skipped Issues

### WR-03: collect() loads all data to driver memory

**File:** `jobs/csv_to_parquet/adapters/secondary/spark_adapter.py:34`
**Reason:** Architectural change required - would need to refactor transform ports to work with DataFrames instead of list[dict]. Added a comment in the code noting this concern for future consideration.
**Original issue:** `df.collect()` pulls all data from the Spark cluster to the driver node. For large datasets, this will cause out-of-memory errors.

---

_Fixed: 2026-08-09T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
