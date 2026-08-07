# Test Suite

This directory contains the full pytest suite for the template_etl project.

## Structure

- `conftest.py` — Session-scoped SparkSession fixture (`spark_session`) and the D-08 invariant
  test (`test_no_aws_sdk_imports`) that kills the suite if any prohibited import appears.
- `unit/` — Unit tests for the pure transforms module. Run without Glue or AWS:
  `pytest tests/unit/`.
- `integration/` — Integration tests that run the full job via subprocess spark-submit and assert
  on the output. Run against the Floci emulator: `pytest tests/integration/`.

## Running Tests

### Inside the container (recommended)

All tests run inside the Glue container via:

    ./run.sh test

This runs unit tests and integration tests together.

### Unit tests only (outside the container)

With only pyspark installed:

    python -m pytest tests/unit/ -v

### Skip Athena tests (escape hatch)

If Athena is unavailable, skip the Athena-dependent tests:

    pytest -m "not athena" tests/

This runs all tests except those marked with `pytest.mark.athena`.

## Invariants

- `test_no_aws_sdk_imports` (conftest.py): This test runs before any other test. It fails the
  entire suite if any file under `transforms/` or `tests/unit/` imports `awsglue` or `boto3`.
  This is the executable form of the D-08 promise: unit tests run without Glue or AWS.
  Do not skip, xfail, or remove this test.

## Test Markers

- `athena` — Tests that query the result via Athena (DuckDB-backed in Floci). These tests are
  skipped by default with `-m "not athena"`. They require the Floci Athena endpoint to be
  available (which it is when running via `./run.sh test`).

## SQL Portable Subset

Integration tests use a portable SQL subset verified against Floci's DuckDB-backed Athena:
SELECT, COUNT(*), AVG, WHERE, GROUP BY, ORDER BY, basic arithmetic.

Not covered: JOINs, window functions, complex date arithmetic, UNION, subqueries.
Divergences from real Athena/Trino land in docs/KNOWN_DIFFERENCES.md (Phase 4).
