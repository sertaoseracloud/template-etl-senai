"""ETL job entry point: csv_to_parquet.

Thin entrypoint using hexagonal architecture.
All orchestration is delegated to GlueAdapter via DI container.

No S3A committer is explicitly configured here - see adapters/ for details.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the project root is on the Python path.
sys.path.insert(0, str(Path.cwd()))

from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import SparkSession

from jobs.csv_to_parquet.application.dto import JobRequest
from jobs.csv_to_parquet.infrastructure.di import get_container
from jobs.csv_to_parquet.infrastructure.config import apply_s3a_config, get_bucket_names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--JOB_NAME", required=True)
    parser.add_argument("--file-key", required=False, default=None)
    args = parser.parse_args()

    file_key = args.file_key if args.file_key else os.environ.get("FILE_KEY")

    spark = SparkSession.builder.appName(args.JOB_NAME).getOrCreate()
    try:
        apply_s3a_config(spark)
        raw_bucket, curated_bucket = get_bucket_names()

        glue_context = GlueContext(spark.sparkContext)
        logger = glue_context.get_logger()

        # Get adapter from DI container
        container = get_container()
        adapter = container.get_glue_adapter(spark, logger)

        # Execute job
        request = JobRequest(
            job_name=args.JOB_NAME,
            file_key=file_key,
            raw_bucket=raw_bucket,
            curated_bucket=curated_bucket,
        )

        result = adapter.run(request)

        # Job lifecycle
        job = Job(glue_context)
        job.init(args.JOB_NAME, vars(args))

        if result.status.value == "completed":
            print("=" * 43)
            print("ETL Job Complete: csv_to_parquet")
            print("=" * 43)
            print(f"Rows read   : {result.rows_read}")
            print(f"Rows written: {result.rows_written}")
            print(f"Input path  : {result.input_path}")
            print(f"Output path : {result.output_path}")
            print("=" * 43)
        else:
            print(f"Job failed: {result.error_message}", file=sys.stderr)
            sys.exit(1)

        job.commit()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
