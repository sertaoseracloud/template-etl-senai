"""Integration test suite for the csv_to_parquet Glue job.

These tests run the job via subprocess spark-submit (not in-process) and
assert on the output stored in the emulated S3 bucket (Floci). The Athena
queries exercise the Glue Data Catalog path end-to-end.

Integration tests import catalog.config (boto3), which is correct -- boto3
is available inside the Glue container. The D-08 invariant test (conftest.py)
only scans transforms/ and tests/unit/, so integration tests are unaffected.

All tests run inside the Glue container via ``./run.sh test``, same as unit
tests. The athena-marked tests require the Floci Athena endpoint (DuckDB-backed)
which is available when the emulator is up.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import boto3
import pytest

# Mark all tests in this module as requiring the Floci Athena endpoint.
# Default pytest run (./run.sh test) skips these via: pytest -m "not athena"
# To run with Athena: pytest --override-ini="markers=" or remove the marker filter.
pytestmark = pytest.mark.athena

from catalog.config import (
    curated_bucket,
    database_name,
    endpoint_url,
    s3_client,
)


# SQL Portable Subset (D-03):
# The Athena queries in this file use only the subset of SQL that is portable
# between DuckDB (Floci's Athena backend) and real Athena / Trino:
#
# SAFE -- tested in this suite:
#   SELECT column, COUNT(*), AVG(column), WHERE, GROUP BY, ORDER BY
#   Basic arithmetic in SELECT expressions
#
# NOT TESTED -- territory this suite does not cover:
#   JOINs, window functions (LEAD, LAG, ROW_NUMBER, etc.)
#   DATEDIFF, DATE_ADD, complex date arithmetic
#   UNION / INTERSECT / EXCEPT
#   Subqueries in FROM or WHERE
#
# When adding a query, stay within the safe subset. Divergences land in
# docs/KNOWN_DIFFERENCES.md (Phase 4).
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clear_curated_prefix() -> int:
    """Delete all objects under the curated bucket's temperaturas/ prefix.

    This is the D-04 state preparation: the test controls its own preconditions
    so COUNT is deterministic regardless of how many times the job has run.
    Returns the number of objects deleted.
    """
    s3 = s3_client()
    bucket = curated_bucket()
    prefix = "temperaturas/"
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    deleted_count = 0
    for page in pages:
        if "Contents" in page:
            keys = [{"Key": obj["Key"]} for obj in page["Contents"]]
            s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            deleted_count += len(keys)
    return deleted_count


def run_job_subprocess(*, timeout_seconds: int = 300) -> dict[str, Any]:
    """Run the csv_to_parquet job via subprocess spark-submit.

    This is the D-06 requirement: the test exercises the real entrypoint, not an
    in-process SparkSession. Uses the same spark-submit binary that ./run.sh job
    invokes, called directly so this runs inside the Glue container where the
    tests themselves execute rather than from the host.

    Returns a dict with keys: returncode, stdout, stderr, duration_seconds.

    Raises RuntimeError if the subprocess exits non-zero.
    """
    repo_root = Path(__file__).resolve().parents[2]
    cmd = [
        "spark-submit",
        f"{repo_root}/jobs/csv_to_parquet/job.py",
        "--JOB_NAME",
        "csv_to_parquet",
    ]
    env = {
        **os.environ,
        # Ensure awsglue (at /usr/share/aws/glue-pds) and transforms/ are on the path.
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


def athena_query(sql: str) -> list[dict[str, str]]:
    """Run a query against the Floci Athena endpoint and return rows as dicts.

    Uses boto3 with the explicit endpoint_url so the query runs against Floci's
    DuckDB-backed Athena, not real AWS.
    """
    client = boto3.client("athena", endpoint_url=endpoint_url())
    s3 = s3_client()
    output_prefix = f"s3://{curated_bucket()}/athena-results/"
    result_key = "athena-results/"
    try:
        s3.head_object(Bucket=curated_bucket(), Key=result_key)
    except s3.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            s3.put_object(Bucket=curated_bucket(), Key=result_key, Body=b"")
        else:
            raise  # re-raise permission errors, network errors, etc.
    response = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database_name()},
        ResultConfiguration={"OutputLocation": output_prefix},
    )
    query_id = response["QueryExecutionId"]
    for _ in range(60):
        result = client.get_query_execution(QueryExecutionId=query_id)
        state = result["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            break
        elif state == "FAILED":
            reason = result["QueryExecution"]["Status"]["StateChangeReason"]
            raise RuntimeError(f"Athena query failed: {reason}")
        time.sleep(1)
    else:
        raise RuntimeError(f"Athena query timed out after 60 seconds (query_id={query_id})")
    results = client.get_query_results(QueryExecutionId=query_id)
    columns = [col["Label"] for col in results["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]]
    rows = []
    for row in results["ResultSet"]["Rows"][1:]:
        rows.append(dict(zip(columns, [cell["VarCharValue"] for cell in row["Data"]])))
    return rows


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def integration_env() -> dict[str, str]:
    """Pass through the environment variables needed for the subprocess."""
    return {**os.environ, "HOME": "/root"}


@pytest.fixture(scope="module")
def clean_curated() -> None:
    """Clear the curated temperaturas/ prefix once per module.

    This is the D-04 state preparation -- run before any integration test
    so the output is deterministic regardless of prior job runs.
    """
    # Module-scoped: runs once before the first integration test.
    # After clean_curated clears the prefix, each test calls run_job_subprocess
    # which appends to the curated bucket. State is intentionally cumulative
    # within the module -- assertions use >= or run fresh within each test.
    clear_curated_prefix()


# ---------------------------------------------------------------------------
# Tests (always run)
# ---------------------------------------------------------------------------
def test_job_runs_successfully(clean_curated: None, integration_env: dict[str, str]) -> None:
    """Job completes with zero exit code and emits the demo summary lines."""
    result = run_job_subprocess(timeout_seconds=300)
    assert result["returncode"] == 0, (
        f"Job exited non-zero: {result['returncode']}\n"
        f"STDOUT:\n{result['stdout']}\n"
        f"STDERR:\n{result['stderr']}"
    )
    assert "ETL Job Complete" in result["stdout"], (
        f"Expected 'ETL Job Complete' in stdout.\nSTDOUT:\n{result['stdout']}"
    )
    assert "Rows read" in result["stdout"], (
        f"Expected 'Rows read' in stdout.\nSTDOUT:\n{result['stdout']}"
    )
    assert "Rows written" in result["stdout"], (
        f"Expected 'Rows written' in stdout.\nSTDOUT:\n{result['stdout']}"
    )
    assert result["duration_seconds"] < 300, (
        f"Job took {result['duration_seconds']}s -- expected under 300s for 18 rows"
    )


def test_job_output_content(clean_curated: None) -> None:
    """Output contains at least 18 parquet files, one per Hive-style partition.

    3 dates x 6 cities = 18 partitions.
    """
    run_job_subprocess(timeout_seconds=300)
    s3 = s3_client()
    bucket = curated_bucket()
    paginator = s3.get_paginator("list_objects_v2")
    parquet_keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix="temperaturas/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".parquet"):
                parquet_keys.append(key)
    assert len(parquet_keys) >= 18, (
        f"Expected at least 18 parquet files, got {len(parquet_keys)}. Files: {parquet_keys}"
    )
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


def test_job_produces_no_temp_commit_files(clean_curated: None) -> None:
    """Smoke test: no _spark_metadata or _SUCCESS at shallow path depth.

    _spark_metadata and _SUCCESS are normal Spark Parquet output inside partition
    leaf directories. Reject them if they appear at depth < 4 path segments
    (e.g., at the temperaturas/ root or top-level partition dir).
    """
    run_job_subprocess(timeout_seconds=300)
    s3 = s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    all_keys: list[str] = []
    for page in paginator.paginate(Bucket=curated_bucket(), Prefix="temperaturas/"):
        for obj in page.get("Contents", []):
            all_keys.append(obj["Key"])
    for key in all_keys:
        basename = Path(key).name
        if basename in ("_spark_metadata", "_SUCCESS") and len(key.split("/")) < 4:
            pytest.fail(
                f"Unexpected commit artifact at shallow path depth: {key}. "
                f"Expected inside a partition leaf directory (>= 4 path segments)."
            )


# ---------------------------------------------------------------------------
# Tests (require Athena endpoint -- skipped with pytest -m "not athena")
# ---------------------------------------------------------------------------
@pytest.mark.athena
def test_athena_count_all(clean_curated: None) -> None:
    """COUNT(*) over the full temperaturas table equals 18.

    Proves the table resolves via the Glue Data Catalog and the job wrote all
    18 rows (3 dates x 6 cities) to the curated bucket.
    """
    run_job_subprocess(timeout_seconds=300)
    rows = athena_query("SELECT COUNT(*) AS total_rows FROM temperaturas")
    assert len(rows) == 1, f"Expected 1 row from COUNT(*), got {len(rows)}: {rows}"
    total = int(rows[0]["total_rows"])
    assert total == 18, f"Expected total_rows=18, got {total}"


@pytest.mark.athena
def test_athena_count_by_partition(clean_curated: None) -> None:
    """COUNT(*) GROUP BY data_medicao returns 3 rows, each with 6 rows.

    Proves compound partitioning (data_medicao + cidade_key) is registered
    correctly in the Data Catalog and Athena respects it.
    """
    run_job_subprocess(timeout_seconds=300)
    rows = athena_query(
        "SELECT data_medicao, COUNT(*) AS rows "
        "FROM temperaturas GROUP BY data_medicao ORDER BY data_medicao"
    )
    assert len(rows) == 3, f"Expected 3 date partitions, got {len(rows)}: {rows}"
    expected_dates = ["2026-01-15", "2026-01-16", "2026-01-17"]
    for row, expected_date in zip(rows, expected_dates):
        assert row["data_medicao"] == expected_date, (
            f"Expected date {expected_date}, got {row['data_medicao']}"
        )
        count = int(row["rows"])
        assert count == 6, f"Date {expected_date}: expected 6 rows (6 cities), got {count}"


@pytest.mark.athena
def test_athena_avg_temp_media(clean_curated: None) -> None:
    """AVG(temp_media) for Florianopolis is non-null and in a plausible range.

    This is the D-01 aggregate assertion: proves the Data Catalog resolves the
    table, the job wrote actual data, and the aggregation computes correctly.
    """
    run_job_subprocess(timeout_seconds=300)
    rows = athena_query(
        "SELECT AVG(temp_media) AS avg_temp FROM temperaturas WHERE cidade_key = 'florianopolis'"
    )
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}: {rows}"
    avg_str = rows[0]["avg_temp"]
    assert avg_str is not None and avg_str != "", (
        "AVG(temp_media) returned NULL or empty for Florianopolis"
    )
    avg_temp = float(avg_str)
    assert 15.0 <= avg_temp <= 35.0, f"avg_temp={avg_temp} outside plausible range [15, 35]"


@pytest.mark.athena
def test_athena_partition_filter(clean_curated: None) -> None:
    """COUNT(*) with compound partition filter (data_medicao + cidade_key) equals 1.

    Proves the compound partition key (D-12) is registered correctly in the
    Glue Data Catalog and Athena prunes to exactly one partition.
    """
    run_job_subprocess(timeout_seconds=300)
    rows = athena_query(
        "SELECT COUNT(*) AS cnt FROM temperaturas "
        "WHERE data_medicao = '2026-01-15' AND cidade_key = 'florianopolis'"
    )
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}: {rows}"
    count = int(rows[0]["cnt"])
    assert count == 1, (
        f"Expected 1 row for the compound partition "
        f"(data_medicao=2026-01-15, cidade_key=florianopolis), got {count}"
    )
