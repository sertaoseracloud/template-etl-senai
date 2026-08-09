#!/usr/bin/env python3
"""Validate ETL results using PySpark.

Validates Parquet data by reading it directly via Spark.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from catalog import config


def validate_with_spark() -> dict:
    """Validate ETL results using PySpark.

    Returns:
        Dict with validation results.
    """
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    print("\n🔍 Validating with PySpark...")

    results = {
        "parquet_files": [],
        "queries": [],
        "valid": True,
        "errors": [],
    }

    try:
        # Create Spark session
        spark = SparkSession.builder \
            .appName("etl-validation") \
            .config("spark.hadoop.fs.s3a.endpoint", config.endpoint_url()) \
            .config("spark.hadoop.fs.s3a.access.key", "test") \
            .config("spark.hadoop.fs.s3a.secret.key", "test") \
            .config("spark.hadoop.fs.s3a.path.style.access", "true") \
            .config("spark.sql.adaptive.enabled", "true") \
            .getOrCreate()

        bucket = config.curated_bucket()
        table_path = f"s3a://{bucket}/temperaturas"

        print(f"  Reading from: {table_path}")

        # Read parquet data
        df = spark.read.parquet(table_path)

        print(f"  ✓ Loaded {df.count()} total rows")
        print("  ✓ Schema:")
        df.printSchema()

        results["queries"].append({
            "name": "total_rows",
            "result": df.count(),
        })

        # Query 1: Count by city
        print("\n  📊 Rows by city:")
        city_counts = df.groupBy("cidade_key").count().orderBy("cidade_key")
        city_counts.show()

        results["queries"].append({
            "name": "city_counts",
            "result": {row["cidade_key"]: row["count"] for row in city_counts.collect()},
        })

        # Query 2: Temperature statistics
        print("\n  🌡️ Temperature statistics:")
        stats_row = df.select(
            F.avg("temp_min").alias("avg_min"),
            F.avg("temp_max").alias("avg_max"),
            F.min("temp_min").alias("min_min"),
            F.max("temp_max").alias("max_max"),
        ).collect()[0]

        print(f"    Avg temp_min: {stats_row['avg_min']:.1f}°C")
        print(f"    Avg temp_max: {stats_row['avg_max']:.1f}°C")
        print(f"    Min temp_min: {stats_row['min_min']:.1f}°C")
        print(f"    Max temp_max: {stats_row['max_max']:.1f}°C")

        results["queries"].append({
            "name": "temperature_stats",
            "result": {
                "avg_temp_min": round(stats_row["avg_min"], 2),
                "avg_temp_max": round(stats_row["avg_max"], 2),
                "min_temp_min": round(stats_row["min_min"], 2),
                "max_temp_max": round(stats_row["max_max"], 2),
            },
        })

        # Query 3: Sample data
        print("\n  📋 Sample data (5 rows):")
        sample = df.orderBy("cidade_key", "data_medicao").limit(5)
        sample.show()

        results["queries"].append({
            "name": "sample",
            "result": sample.count(),
        })

        # Query 4: Partition info
        print("\n  📁 Partition info:")
        partitions = df.select("data_medicao", "cidade_key").distinct().orderBy("data_medicao", "cidade_key")
        partitions.show(truncate=False)

        results["queries"].append({
            "name": "partitions",
            "result": partitions.count(),
        })

        spark.stop()

    except Exception as e:
        results["valid"] = False
        results["errors"].append(str(e))
        import traceback
        traceback.print_exc()
        print(f"    ✗ Error: {e}")

    return results


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate ETL results via PySpark")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    results = validate_with_spark()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 50)
        print("Validation complete!")
        print("=" * 50)

    return 0 if results["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
