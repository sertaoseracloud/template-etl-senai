"""ETL job entry point: csv_to_parquet (hexagonal architecture)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import SparkSession

from jobs.csv_to_parquet.application.dto import JobRequest
from jobs.csv_to_parquet.infrastructure.config import apply_s3a_config, get_bucket_names
from jobs.csv_to_parquet.infrastructure.di import get_container


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--JOB_NAME", required=True)
    p.add_argument("--file-key", required=False, default=None)
    args = p.parse_args()
    spark = SparkSession.builder.appName(args.JOB_NAME).getOrCreate()
    try:
        apply_s3a_config(spark)
        raw, curated = get_bucket_names()
        logger = GlueContext(spark.sparkContext).get_logger()
        adapter = get_container().get_glue_adapter(spark, logger)
        request = JobRequest(
            job_name=args.JOB_NAME,
            file_key=args.file_key or os.environ.get("FILE_KEY"),
            raw_bucket=raw,
            curated_bucket=curated,
        )
        Job(GlueContext(spark.sparkContext)).init(args.JOB_NAME, vars(args))
        result = adapter.run(request)
        if result.status.value == "completed":
            print(f"ETL Complete: {result.rows_read} read, {result.rows_written} written")
        else:
            print(f"Job failed: {result.error_message}", file=sys.stderr)
            sys.exit(1)
        Job(GlueContext(spark.sparkContext)).commit()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
