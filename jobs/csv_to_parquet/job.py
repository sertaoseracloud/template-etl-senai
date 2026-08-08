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


def apply_s3a_config(spark: SparkSession) -> tuple[str, str]:
    """Apply S3A configuration and return bucket names.

    Bucket derivation matches catalog/config.py:
    - raw_bucket = f"{project_name.replace('_', '-')}-raw"
    - curated_bucket = f"{project_name.replace('_', '-')}-curated"
    """
    project_name = os.environ["PROJECT_NAME"]
    raw_bucket = f"{project_name.replace('_', '-')}-raw"
    curated_bucket = f"{project_name.replace('_', '-')}-curated"

    hconf = spark.sparkContext._jsc.hadoopConfiguration()
    hconf.set("fs.s3a.endpoint", os.environ["AWS_ENDPOINT_URL"])
    hconf.set("fs.s3a.path.style.access", "true")
    hconf.set("fs.s3a.connection.ssl.enabled", "false")
    hconf.set(
        "fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    )
    hconf.set("fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
    hconf.set("fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
    hconf.set("fs.s3a.endpoint.region", os.environ["AWS_DEFAULT_REGION"])

    return raw_bucket, curated_bucket


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--JOB_NAME", required=True)
    parser.add_argument("--file-key", required=False, default=None)
    args = parser.parse_args()

    file_key = args.file_key if args.file_key else os.environ.get("FILE_KEY")

    spark = SparkSession.builder.appName(args.JOB_NAME).getOrCreate()
    try:
        raw_bucket, curated_bucket = apply_s3a_config(spark)

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
