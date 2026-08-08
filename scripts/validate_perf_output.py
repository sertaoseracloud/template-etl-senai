#!/usr/bin/env python3
"""Validate ETL benchmark results against S3 storage.

Validates that generated test files exist in S3 and have correct content.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

# Add parent directory to path for catalog imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from catalog import config


def validate_s3_object(bucket: str, key: str, expected_rows: int | None = None) -> dict:
    """Validate a single S3 object exists and optionally check row count.

    Args:
        bucket: S3 bucket name.
        key: S3 object key.
        expected_rows: Expected number of data rows (excluding header).

    Returns:
        Dict with validation results.
    """
    s3 = config.s3_client()

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")

        # Parse CSV
        reader = csv.reader(io.StringIO(content))
        header = next(reader)
        rows = list(reader)

        result = {
            "key": key,
            "exists": True,
            "size_bytes": len(content),
            "row_count": len(rows),
            "header": header,
            "valid": True,
            "error": None,
        }

        # Validate header
        expected_header = ["cidade", "cidade_key", "data_medicao", "temp_min", "temp_max"]
        if header != expected_header:
            result["valid"] = False
            result["error"] = f"Header mismatch: expected {expected_header}, got {header}"

        # Validate row count
        if expected_rows is not None and len(rows) != expected_rows:
            result["valid"] = False
            result["error"] = f"Row count mismatch: expected {expected_rows}, got {len(rows)}"

        # Validate data integrity
        if result["valid"]:
            for i, row in enumerate(rows[:5]):  # Check first 5 rows
                if len(row) != 5:
                    result["valid"] = False
                    result["error"] = f"Row {i} has {len(row)} columns, expected 5"
                    break

        return result

    except s3.exceptions.NoSuchKey:
        return {
            "key": key,
            "exists": False,
            "valid": False,
            "error": "Object not found in S3",
        }
    except Exception as e:
        return {
            "key": key,
            "exists": False,
            "valid": False,
            "error": str(e),
        }


def validate_perf_test_output(n_rows: int) -> dict:
    """Validate performance test output for a given row count.

    Args:
        n_rows: Number of rows that were generated.

    Returns:
        Dict with validation results.
    """
    bucket = config.raw_bucket()
    key = f"temperaturas/perf_test_{n_rows}.csv"

    return validate_s3_object(bucket, key, n_rows)


def run_validation(n_rows: int) -> bool:
    """Run validation for a performance test.

    Args:
        n_rows: Number of rows to validate.

    Returns:
        True if validation passes, False otherwise.
    """
    result = validate_perf_test_output(n_rows)

    print(f"\nValidation for {n_rows:,} rows:")
    print(f"  Key: {result['key']}")
    print(f"  Exists: {result['exists']}")

    if result["exists"]:
        print(f"  Size: {result['size_bytes']:,} bytes")
        print(f"  Rows: {result['row_count']:,}")
        print(f"  Valid: {result['valid']}")

    if result["error"]:
        print(f"  Error: {result['error']}")

    return result["valid"]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate ETL performance test output against S3."
    )
    parser.add_argument(
        "--rows",
        type=int,
        required=True,
        help="Number of rows to validate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON.",
    )

    args = parser.parse_args()

    result = validate_perf_test_output(args.rows)

    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        success = run_validation(args.rows)
        return 0 if success else 1

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
