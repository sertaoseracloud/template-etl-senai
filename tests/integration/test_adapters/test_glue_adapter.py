"""End-to-end integration tests for GlueAdapter.

These tests exercise the GlueAdapter with real Spark and Floci S3,
verifying the full hexagonal architecture integration.

Tests run via subprocess spark-submit (not in-process Spark) following
the same pattern as test_job.py to ensure realistic execution context.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from pyspark.sql import SparkSession

from catalog.config import (  # noqa: E402  # boto3 available in Glue container
    curated_bucket,
    endpoint_url,
    s3_client,
)
from jobs.csv_to_parquet.adapters.primary.glue_adapter import GlueAdapter
from jobs.csv_to_parquet.adapters.secondary.spark_adapter import SparkAdapter
from jobs.csv_to_parquet.application.dto import JobRequest
from jobs.csv_to_parquet.application.use_cases import ProcessCsvUseCase
from jobs.csv_to_parquet.domain.entities import JobStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class MockLogger:
    """Minimal mock logger implementing the interface expected by GlueAdapter."""

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def spark_session():
    """Return a module-scoped SparkSession configured for S3A access."""
    builder = SparkSession.builder
    for key, value in {
        "spark.sql.shuffle.partitions": "4",
        "spark.ui.enabled": "false",
        "spark.hadoop.fs.s3a.access.key": "test",
        "spark.hadoop.fs.s3a.secret.key": "test",
        "spark.hadoop.fs.s3a.endpoint": endpoint_url(),
        "spark.hadoop.fs.s3a.path.style.access": "true",
    }.items():
        builder = builder.config(key, value)
    spark = builder.getOrCreate()
    yield spark
    spark.stop()


@pytest.fixture(scope="function")
def clean_curated(clean_curated_prefix):
    """Ensure curated bucket is clean before each test.

    Delegates to clean_curated_prefix which performs the actual cleanup.
    """
    # clean_curated_prefix handles pre-test cleanup
    yield


# ---------------------------------------------------------------------------
# Subprocess-based Integration Tests
# ---------------------------------------------------------------------------
def run_glue_adapter_subprocess(timeout_seconds: int = 300) -> dict[str, Any]:
    """Run the csv_to_parquet job via subprocess spark-submit.

    This exercises the real entrypoint with GlueAdapter, same as test_job.py.

    Returns a dict with keys: returncode, stdout, stderr, duration_seconds.

    Raises RuntimeError if the subprocess exits non-zero.
    """
    repo_root = Path(__file__).resolve().parents[4]
    cmd = [
        "spark-submit",
        f"{repo_root}/jobs/csv_to_parquet/job.py",
        "--JOB_NAME",
        "csv_to_parquet",
    ]
    env = {
        **os.environ,
        "PYTHONPATH": f"/usr/share/aws/glue-pds:{repo_root}",
    }
    start = time.monotonic()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_seconds,
    )
    duration = time.monotonic() - start
    outcome = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_seconds": round(duration, 2),
    }
    if result.returncode != 0:
        raise RuntimeError(
            f"Job subprocess failed (exit {result.returncode})\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return outcome


def count_parquet_files() -> int:
    """Count parquet files in the curated bucket's temperaturas/ prefix."""
    s3 = s3_client()
    bucket = curated_bucket()
    paginator = s3.get_paginator("list_objects_v2")
    parquet_keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix="temperaturas/"):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                parquet_keys.append(obj["Key"])
    return len(parquet_keys)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_glue_adapter_runs_via_subprocess(clean_curated: None) -> None:
    """GlueAdapter job completes with zero exit code and expected output."""
    result = run_glue_adapter_subprocess(timeout_seconds=300)
    assert result["returncode"] == 0, (
        f"Job exited non-zero: {result['returncode']}\n"
        f"STDOUT:\n{result['stdout']}\n"
        f"STDERR:\n{result['stderr']}"
    )
    assert "ETL Job Complete" in result["stdout"], (
        f"Expected 'ETL Job Complete' in stdout.\nSTDOUT:\n{result['stdout']}"
    )


def test_glue_adapter_job_status_completed(clean_curated: None) -> None:
    """Job completes with COMPLETED status and populated metrics."""
    result = run_glue_adapter_subprocess(timeout_seconds=300)
    stdout = result["stdout"]

    # Verify status indicators in output
    assert "COMPLETED" in stdout or "COMPLETE" in stdout or "ETL Job Complete" in stdout, (
        f"Expected job completion indicator in output.\nSTDOUT:\n{stdout}"
    )

    # Verify rows_read is populated
    assert "Rows read" in stdout, f"Expected 'Rows read' in stdout.\nSTDOUT:\n{stdout}"

    # Verify rows_written is populated
    assert "Rows written" in stdout, f"Expected 'Rows written' in stdout.\nSTDOUT:\n{stdout}"


def test_glue_adapter_populates_rows_metrics(clean_curated: None) -> None:
    """Verify rows_read and rows_written are positive numbers."""
    result = run_glue_adapter_subprocess(timeout_seconds=300)
    stdout = result["stdout"]

    # Parse rows read from output
    rows_read_match = re.search(r"Rows read[:\s]+(\d+)", stdout, re.IGNORECASE)
    rows_written_match = re.search(r"Rows written[:\s]+(\d+)", stdout, re.IGNORECASE)

    assert rows_read_match is not None, f"Could not find 'Rows read' in output.\nSTDOUT:\n{stdout}"
    assert rows_written_match is not None, (
        f"Could not find 'Rows written' in output.\nSTDOUT:\n{stdout}"
    )

    rows_read = int(rows_read_match.group(1))
    rows_written = int(rows_written_match.group(1))

    assert rows_read > 0, f"Expected positive rows_read, got {rows_read}"
    assert rows_written > 0, f"Expected positive rows_written, got {rows_written}"


def test_glue_adapter_output_parquet_files_exist(clean_curated: None) -> None:
    """Output parquet files exist in curated bucket after job completion."""
    run_glue_adapter_subprocess(timeout_seconds=300)

    # Verify parquet files exist
    parquet_count = count_parquet_files()
    # 3 dates x 6 cities = 18 partitions
    assert parquet_count >= 18, (
        f"Expected at least 18 parquet files (3 dates x 6 cities), got {parquet_count}"
    )


def test_glue_adapter_in_process(
    spark_session: SparkSession,
    clean_curated: None,
) -> None:
    """Test GlueAdapter directly in-process with real Spark + Floci S3.

    This tests the adapter's direct integration without subprocess overhead,
    verifying the hexagonal architecture wiring is correct.
    """
    # Initialize adapter components
    spark_adapter = SparkAdapter(spark_session)
    use_case = ProcessCsvUseCase(
        storage=spark_adapter,
        transformer=spark_adapter,
    )
    logger = MockLogger()
    adapter = GlueAdapter(
        spark=spark_session,
        use_case=use_case,
        logger=logger,
    )

    # Create job request
    project = os.environ.get("PROJECT_NAME", "template_etl").replace("_", "-")
    request = JobRequest(
        job_name="csv_to_parquet",
        file_key=None,
        raw_bucket=f"{project}-raw",
        curated_bucket=f"{project}-curated",
        partition_cols=["data_medicao", "cidade_key"],
    )

    # Run the adapter
    result = adapter.run(request)

    # Verify job completed successfully
    assert result.status == JobStatus.COMPLETED, f"Expected status COMPLETED, got {result.status}"

    # Verify metrics are populated
    assert result.rows_read > 0, f"Expected positive rows_read, got {result.rows_read}"
    assert result.rows_written > 0, f"Expected positive rows_written, got {result.rows_written}"

    # Verify output path is set
    assert result.output_path, "Expected non-empty output_path"

    # Verify parquet files exist in S3
    parquet_count = count_parquet_files()
    # 3 dates x 6 cities = 18 partitions
    assert parquet_count >= 18, f"Expected >=18 parquet files (3x6 partitions), got {parquet_count}"


def test_glue_adapter_parquet_partition_structure(clean_curated: None) -> None:
    """Verify output parquet files follow expected partition structure."""
    run_glue_adapter_subprocess(timeout_seconds=300)

    s3 = s3_client()
    bucket = curated_bucket()
    paginator = s3.get_paginator("list_objects_v2")
    parquet_keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix="temperaturas/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".parquet"):
                parquet_keys.append(key)

    # Verify expected partition keys are present
    expected_dates = {"2026-01-15", "2026-01-16", "2026-01-17"}
    expected_cities = {
        "florianopolis",
        "joinville",
        "blumenau",
        "chapeco",
        "lages",
        "criciuma",
    }

    found_dates: set[str] = set()
    found_cities: set[str] = set()
    for key in parquet_keys:
        for part in key.split("/"):
            if part.startswith("data_medicao="):
                found_dates.add(part.split("=", 1)[1])
            if part.startswith("cidade_key="):
                found_cities.add(part.split("=", 1)[1])

    assert found_dates == expected_dates, f"Expected dates {expected_dates}, found {found_dates}"
    assert found_cities == expected_cities, (
        f"Expected cities {expected_cities}, found {found_cities}"
    )
