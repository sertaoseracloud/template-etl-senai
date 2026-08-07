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

import os
import sys
import argparse

from pyspark.sql import SparkSession
from awsglue.context import GlueContext
from awsglue.job import Job

from transforms import read_csv, derive_temp_media, add_city_key, write_parquet


def apply_s3a_config(spark: SparkSession) -> SparkSession:
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
    aws_region = os.environ["AWS_REGION"]
    s3_endpoint = os.environ["S3_ENDPOINT"]
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
    args = parser.parse_args()

    spark = (
        SparkSession.builder.appName(args.JOB_NAME).getOrCreate()
    )
    spark, project_name_raw_bucket, project_name_curated_bucket = apply_s3a_config(spark)

    glue_context = GlueContext(spark.sparkContext)
    job = Job(glue_context)
    job.init(args.JOB_NAME, args)

    raw_path = f"s3a://{project_name_raw_bucket}/temperaturas/"
    raw_df = read_csv(spark, raw_path)
    rows_read = raw_df.count()

    df = add_city_key(raw_df)
    df = derive_temp_media(df)

    if df.count() == 0:
        sys.exit(
            "Job output is empty. Aborting -- check input data at: " + raw_path
        )

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
    print(f"Partitions  : 18 (data_medicao x cidade_key)")
    print(f"Input path  : s3a://{project_name_raw_bucket}/temperaturas/")
    print(f"Output path : s3a://{project_name_curated_bucket}/temperaturas/")
    print("=" * 43)


if __name__ == "__main__":
    main()
