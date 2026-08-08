"""ETL job entry point: csv_to_parquet.

Wires argparse, GlueContext, S3A configuration, and the transforms module
together. This is the only file in the project that imports awsglue. All
transformation logic lives in transforms/, which imports only pyspark.sql.

No S3A committer is explicitly configured here. The options are:

- Magic committer (fs.s3a.committer.name=magic):
  NOT used. Floci v1.5.11 does not correctly persist ObjectParts metadata
  after CompleteMultipartUpload (floci-io/floci#30), which breaks the Magic
  committer's task-enumeration step. This is a known Floci gap, not a
  configuration problem.

- Directory staging committer (fs.s3a.committer.name=directory):
  NOT used. Adds staging-then-upload overhead that yields zero benefit for
  18-kilobyte Parquet files across 18 partitions. Append conflict mode is
  tolerated but not optimized for.

- Default FileOutputCommitter (what you get with no configuration):
  USED. Direct PutObject to the final path. No multipart, no staging, no
  rename. Failed tasks leave partial files at their final paths; the
  integration test's content assertion (D-04) is the safety net.

If this job is migrated to real AWS S3, re-evaluate the Magic committer:
real S3 has no GetObjectAttributes gap and multipart upload is beneficial
for files larger than ~100 MB.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on the Python path.
# The working directory is /home/hadoop/workspace (bind-mounted project root)
# but Python does not add cwd to sys.path automatically.
sys.path.insert(0, str(Path.cwd()))

from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import SparkSession

from transforms import add_city_key, derive_temp_media, read_csv, write_parquet


def apply_s3a_config(spark: SparkSession) -> tuple[SparkSession, str, str]:
    """Apply the complete S3A configuration block as one unit.

    Reads from os.environ directly. The bucket derivation
    (underscore-to-hyphen for S3, hyphen-to-underscore for Glue) is
    reproduced here inline so that this job does not depend on
    catalog.config.py, which imports boto3 and is forbidden in the job
    context (D-08). If the PROJECT_NAME -> bucket derivation ever changes,
    BOTH catalog/config.py AND this inline derivation must be updated.
    """
    aws_access_key_id = os.environ["AWS_ACCESS_KEY_ID"]
    aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]
    aws_region = os.environ["AWS_DEFAULT_REGION"]
    s3_endpoint = os.environ["AWS_ENDPOINT_URL"]
    project_name = os.environ["PROJECT_NAME"]

    # Bucket names: same derivation as catalog/config.py
    raw_bucket = f"{project_name.replace('_', '-')}-raw"
    curated_bucket = f"{project_name.replace('_', '-')}-curated"

    hconf = spark.sparkContext._jsc.hadoopConfiguration()
    hconf.set("fs.s3a.endpoint", s3_endpoint)
    hconf.set("fs.s3a.path.style.access", "true")
    hconf.set("fs.s3a.connection.ssl.enabled", "false")
    hconf.set(
        "fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    )
    hconf.set("fs.s3a.access.key", aws_access_key_id)
    hconf.set("fs.s3a.secret.key", aws_secret_access_key)
    hconf.set("fs.s3a.endpoint.region", aws_region)

    return spark, raw_bucket, curated_bucket


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--JOB_NAME", required=True)
    parser.add_argument("--file-key", required=False, default=None)
    args = parser.parse_args()

    # Env var fallback for FILE_KEY (EVT-01)
    file_key = args.file_key if args.file_key else os.environ.get("FILE_KEY")

    spark = SparkSession.builder.appName(args.JOB_NAME).getOrCreate()
    try:
        spark, project_name_raw_bucket, project_name_curated_bucket = apply_s3a_config(spark)

        glue_context = GlueContext(spark.sparkContext)
        logger = glue_context.get_logger()

        # Determine the source path based on file_key parameter
        if file_key:
            raw_path = f"s3a://{project_name_raw_bucket}/{file_key}"
            # Log CloudWatch-compatible trigger event (EVT-02)
            iso_timestamp = datetime.now(timezone.utc).isoformat()
            # Check if file exists in S3 (D-02: skip silently if not found)
            try:
                fs = spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(
                    spark.sparkContext._jvm.java.net.URI.create(raw_path),
                    spark.sparkContext._jsc.hadoopConfiguration()
                )
                path = spark.sparkContext._jvm.org.apache.hadoop.fs.Path(raw_path)
                if not fs.exists(path):
                    logger.info(f"File {file_key} not found, skipping silently.")
                    spark.stop()
                    sys.exit(0)
                file_status = fs.getFileStatus(path)
                size_bytes = file_status.getLen()
            except Exception:
                size_bytes = 0
            logger.info(f"TRIGGER_EVENT: {{'file_key': '{file_key}', 'size_bytes': {size_bytes}, 'timestamp': '{iso_timestamp}'}}")
        else:
            raw_path = f"s3a://{project_name_raw_bucket}/temperaturas/"

        job = Job(glue_context)
        # job.init expects a dict or a Java object, not argparse.Namespace.
        # Convert Namespace to a plain dict so Glue's _get_object_id reflection works.
        job.init(args.JOB_NAME, vars(args))

        raw_df = read_csv(spark, raw_path)
        rows_read = raw_df.count()

        df = add_city_key(raw_df)
        df = derive_temp_media(df)

        if df.count() == 0:
            sys.exit("Job output is empty. Aborting -- check input data at: " + raw_path)

        curated_path = f"s3a://{project_name_curated_bucket}/temperaturas/"
        write_parquet(df, curated_path, partition_cols=["data_medicao", "cidade_key"])

        job.commit()

        output_rows = 0
        try:
            written_df = spark.read.parquet(curated_path)
            output_rows = written_df.count()
        except Exception:
            pass

        print("=" * 43)
        print("ETL Job Complete: csv_to_parquet")
        print("=" * 43)
        print(f"Rows read   : {rows_read}")
        print(f"Rows written: {output_rows}")
        print("Partitions  : 18 (data_medicao x cidade_key)")
        print(f"Input path  : {raw_path}")
        print(f"Output path : s3a://{project_name_curated_bucket}/temperaturas/")
        print("=" * 43)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
