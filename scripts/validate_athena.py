#!/usr/bin/env python3
"""Validate ETL results via Athena queries.

Uses Floci's Athena emulation to query processed Parquet data.

Athena Modes:
- MOCK mode (FLOCI_SERVICES_ATHENA_MOCK=true): Returns empty results
  - Good for testing Glue catalog setup
  - Works on Windows without additional setup

- DUCK mode (with floci-duck sidecar): Real SQL via DuckDB
  - Enable: docker compose --profile athena up -d
  - Requires: Linux/macOS or WSL2
  - Provides: Real query results from Parquet data

For Windows users: Use validate_spark.py for real validation.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from catalog import config


def wait_for_query(athena, query_execution_id: str, max_wait: int = 60) -> dict:
    """Wait for Athena query to complete.

    Args:
        athena: boto3 Athena client.
        query_execution_id: Query execution ID.
        max_wait: Maximum seconds to wait.

    Returns:
        Query execution status dict.
    """
    start = time.time()
    while time.time() - start < max_wait:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        status = response["QueryExecution"]["Status"]["State"]

        if status == "SUCCEEDED":
            return response
        elif status in ("FAILED", "CANCELLED"):
            reason = response["QueryExecution"]["Status"].get("StateChangeReason", "")
            raise RuntimeError(f"Query {status}: {reason}")

        time.sleep(0.5)

    raise TimeoutError(f"Query timed out after {max_wait}s")


def run_athena_query(query: str, max_wait: int = 60) -> list[dict]:
    """Run an Athena query and return results.

    Args:
        query: SQL query string.
        max_wait: Maximum seconds to wait for completion.

    Returns:
        List of result rows as dicts.
    """
    athena = config.athena_client()

    # Start query
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": config.database_name()},
        ResultConfiguration={"OutputLocation": f"s3://{config.curated_bucket()}/athena-results/"},
    )
    query_execution_id = response["QueryExecutionId"]

    # Wait for completion
    wait_for_query(athena, query_execution_id, max_wait)

    # Get results
    result = athena.get_query_results(QueryExecutionId=query_execution_id)

    # Parse results
    rows = []
    for row in result["ResultSet"]["Rows"][1:]:  # Skip header
        rows.append(
            {
                col["Name"]: val["VarCharValue"]
                for col, val in zip(
                    result["ResultSet"]["ResultSetMetadata"]["ColumnInfo"], row["Data"]
                )
            }
        )

    return rows


def validate_with_athena() -> dict:
    """Validate ETL results using Athena queries.

    Returns:
        Dict with validation results.
    """
    print("\n🔍 Validating with Athena...")

    results = {
        "glue_tables": [],
        "athena_queries": [],
        "valid": True,
        "errors": [],
    }

    try:
        # Check Glue tables
        glue = config.glue_client()

        print("  Checking Glue tables...")
        databases = glue.get_databases()
        db_name = config.database_name()

        for db in databases["DatabaseList"]:
            if db["Name"] == db_name:
                tables = glue.get_tables(DatabaseName=db_name)
                for table in tables["TableList"]:
                    print(f"    ✓ Table: {table['Name']}")
                    results["glue_tables"].append(
                        {
                            "name": table["Name"],
                            "location": table["StorageDescriptor"]["Location"],
                        }
                    )

        # Run Athena queries on temperaturas table
        print("\n  Running Athena queries...")

        # Query 1: Count total rows
        query1 = "SELECT COUNT(*) as total_rows FROM temperaturas"
        rows1 = run_athena_query(query1)
        total = int(rows1[0]["total_rows"]) if rows1 else 0
        print(f"    ✓ Total rows in temperaturas: {total:,}")
        results["athena_queries"].append(
            {
                "query": query1,
                "result": total,
            }
        )

        # Query 2: Count by city
        query2 = """
            SELECT cidade_key, COUNT(*) as count
            FROM temperaturas
            GROUP BY cidade_key
            ORDER BY cidade_key
        """
        rows2 = run_athena_query(query2)
        print("    ✓ Rows by city:")
        for row in rows2:
            print(f"      - {row['cidade_key']}: {row['count']} rows")
        results["athena_queries"].append(
            {
                "query": "GROUP BY cidade_key",
                "result": {r["cidade_key"]: int(r["count"]) for r in rows2},
            }
        )

        # Query 3: Temperature statistics
        query3 = """
            SELECT
                AVG(temp_min) as avg_temp_min,
                AVG(temp_max) as avg_temp_max,
                MIN(temp_min) as min_temp_min,
                MAX(temp_max) as max_temp_max
            FROM temperaturas
        """
        rows3 = run_athena_query(query3)
        if rows3:
            stats = rows3[0]
            print("    ✓ Temperature stats:")
            print(f"      - Avg temp_min: {float(stats['avg_temp_min']):.1f}°C")
            print(f"      - Avg temp_max: {float(stats['avg_temp_max']):.1f}°C")
            print(f"      - Min temp_min: {float(stats['min_temp_min']):.1f}°C")
            print(f"      - Max temp_max: {float(stats['max_temp_max']):.1f}°C")
            results["athena_queries"].append({"query": "temp stats", "result": stats})

        # Query 4: Sample data
        query4 = "SELECT * FROM temperaturas LIMIT 5"
        rows4 = run_athena_query(query4)
        print("    ✓ Sample data (5 rows):")
        for row in rows4:
            data = row["data_medicao"]
            print(f"      {row['cidade_key']}: {row['temp_min']}-{row['temp_max']}°C on {data}")
        results["athena_queries"].append({"query": "sample", "result": len(rows4)})

    except Exception as e:
        results["valid"] = False
        results["errors"].append(str(e))
        print(f"    ✗ Error: {e}")

    return results


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate ETL results via Athena")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    results = validate_with_athena()

    if args.json:
        print(json.dumps(results, indent=2))

    return 0 if results["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
