# Phase 1: Code Review Report - Hexagonal Architecture

**Reviewed:** 2026-08-09T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

The Phase 1 hexagonal architecture refactor establishes a solid ports-and-adapters structure with proper separation of concerns. However, several bugs and quality issues were identified that require attention before shipping.

Critical issues include silent exception swallowing that masks runtime failures, a pattern of catching broad exceptions after specific handlers, and an architectural concern where data is collected to driver memory which will fail on large datasets.

---

## Critical Issues

### CR-01: Silent exception swallowing masks failures

**File:** `jobs/csv_to_parquet/adapters/secondary/spark_adapter.py:59-60`
**Issue:** The `get_file_info` method silently swallows all exceptions with an empty `except` block. If file system operations fail for any reason (permissions, network issues, malformed paths), the method returns `None` without logging or propagating the error. This makes debugging production issues extremely difficult.
**Fix:**
```python
def get_file_info(self, path: str) -> FileInfo | None:
    """Get file information using Hadoop FileSystem."""
    s3a_path = path.replace("s3://", "s3a://")
    try:
        # ... existing logic ...
    except Exception as e:
        import logging
        logging.warning(f"Failed to get file info for {path}: {e}")
        return None
    return None
```

### CR-02: Empty except clause with no handling

**File:** `jobs/csv_to_parquet/application/use_cases.py:76`
**Issue:** The broad `except Exception` block catches all exceptions including `FileNotFoundError`, making the specific handler at line 69 unreachable. This conflates different failure modes and makes error diagnosis impossible.
**Fix:**
```python
except Exception as e:
    # Log the actual exception before wrapping
    return JobResponse(
        success=False,
        input_path=input_path if "input_path" in locals() else "",
        message="Processing failed",
        error=str(e),
    )
```

### CR-03: data_key always reports 0

**File:** `jobs/csv_to_parquet/adapters/primary/glue_adapter.py:58`
**Issue:** The `size_bytes` in the CloudWatch log event is hardcoded to `0` instead of using `result.file_size_bytes` from the job result. This makes monitoring and alerting based on file sizes impossible.
**Fix:**
```python
f"'size_bytes': {result.file_size_bytes}, "
```

---

## Warnings

### WR-01: Output path always batch "temperaturas/" for single file processing

**File:** `jobs/csv_to_parquet/application/use_cases.py:57`
**Issue:** When a specific `file_key` is provided (event-driven mode), the output path is still `s3://{curated_bucket}/temperaturas/` without incorporating the file key. This means all event-driven processed files overwrite each other. The partition structure handles organization, but the base path should distinguish between batch and event-driven processing.
**Fix:**
```python
if request.file_key:
    output_path = f"s3://{request.curated_bucket}/temperaturas/{request.file_key.rsplit('.', 1)[0]}/"
else:
    output_path = f"s3://{request.curated_bucket}/temperaturas/"
```

### WR-02: Unused local variable with fragile workaround

**File:** `jobs/csv_to_parquet/application/use_cases.py:72,79`
**Issue:** The `input_path` variable is only defined inside the try block but referenced in except handlers using `if "input_path" in locals()`. This workaround is fragile and obscures intent. The variable should be initialized before the try block.
**Fix:**
```python
input_path = ""
try:
    # Determine input path
    if request.file_key:
        input_path = f"s3://{request.raw_bucket}/{request.file_key}"
    else:
        input_path = f"s3://{request.raw_bucket}/temperaturas/"
    # ... rest of logic ...
except FileNotFoundError as e:
    return JobResponse(
        success=False,
        input_path=input_path,
        message="File not found",
        error=str(e),
    )
```

### WR-03: collect() loads all data to driver memory

**File:** `jobs/csv_to_parquet/adapters/secondary/spark_adapter.py:34`
**Issue:** `df.collect()` pulls all data from the Spark cluster to the driver node. For large datasets, this will cause out-of-memory errors. The transformation ports work with `list[dict]` (line 17 in transform_port.py, line 63-64 in spark_adapter.py), which forces this inefficient pattern. The architecture should consider working with DataFrames or using distributed processing patterns.
**Fix:** Consider refactoring transform ports to work with DataFrames:
```python
def read_csv(self, path: str) -> DataFrame:  # Return DataFrame, not list[dict]
    s3a_path = path.replace("s3://", "s3a://")
    return self._spark.read.csv(s3a_path, header=True, inferSchema=True)
```

### WR-04: No validation that partition columns exist

**File:** `jobs/csv_to_parquet/application/dto.py:16`
**Issue:** The default `partition_cols` includes `data_medicao` and `cidade_key`, but `cidade_key` is derived during transformation (added by `add_city_key`). If `write_parquet` is called before transformations complete, or if the columns don't exist in input data, Spark will throw an exception. No validation occurs.
**Fix:** Add validation in `ProcessCsvUseCase.execute` after transformations or in the DTO `__post_init__`:
```python
def __post_init__(self) -> None:
    if not self.job_name:
        raise ValueError("job_name is required")
    # Validate partition columns are non-empty list
    if not self.partition_cols:
        raise ValueError("partition_cols cannot be empty")
```

### WR-05: Job.init() called after execution

**File:** `jobs/csv_to_parquet/job.py:38`
**Issue:** `Job(...).init()` is called after `adapter.run(request)` completes, but Glue expects `init()` to be called at the beginning of job execution. This could cause tracking issues in the Glue console. The correct pattern is `init()` -> do work -> `commit()`.
**Fix:**
```python
result = adapter.run(request)
# ... validate result ...
Job(GlueContext(spark.sparkContext)).commit()
```

---

## Info

### IN-01: No bounds checking in CsvRecord.from_dict

**File:** `jobs/csv_to_parquet/domain/entities.py:43-52`
**Issue:** `from_dict` uses `float()` and `str()` on values without checking if keys exist first. Missing keys will raise `KeyError` with unhelpful messages.
**Fix:**
```python
@classmethod
def from_dict(cls, data: dict) -> CsvRecord:
    """Create from dictionary."""
    required_fields = ["cidade", "data_medicao", "temp_min", "temp_max"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    return cls(
        cidade=str(data["cidade"]),
        data_medicao=str(data["data_medicao"]),
        temp_min=float(data["temp_min"]),
        temp_max=float(data["temp_max"]),
        cidade_key=data.get("cidade_key"),
        temp_media=float(data["temp_media"]) if data.get("temp_media") else None,
    )
```

### IN-02: Two SparkAdapter instances created for single adapter

**File:** `jobs/csv_to_parquet/infrastructure/di.py:64-66`
**Issue:** Two separate `SparkAdapter(spark)` instances are created even though the class implements both `StoragePort` and `TransformPort`. This wastes resources and could lead to state inconsistencies if adapters maintain state (they don't currently, but it's a fragile pattern).
**Fix:**
```python
adapter = SparkAdapter(spark)
use_case = ProcessCsvUseCase(adapter, adapter)
return GlueAdapter(spark, use_case, logger)
```

### IN-03: Result.started_at never logged or used

**File:** `jobs/csv_to_parquet/adapters/primary/glue_adapter.py:49,63-73`
**Issue:** `started_at` is captured at line 49 and stored in the JobResult at line 69, but nowhere is it logged or used for metrics. The Glue adapter should log job duration or emit metrics for monitoring.
**Fix:** Add logging before return:
```python
duration_seconds = (datetime.now(UTC) - started_at).total_seconds()
if self._logger:
    self._logger.info(f"Job completed in {duration_seconds:.2f}s")
```

### IN-04: Magic string "temperaturas/" repeated

**File:** `jobs/csv_to_parquet/application/use_cases.py:43,57`
**Issue:** The string `"temperaturas/"` appears in multiple places. If the prefix ever changes, multiple locations must be updated.
**Fix:** Define as a constant at module level or in config:
```python
DEFAULT_DATA_PREFIX = "temperaturas/"
```

---

_Reviewed: 2026-08-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
