"""AWS S3 configuration utilities for Glue jobs.

Provides S3A configuration for PySpark jobs running in AWS Glue.
"""

from __future__ import annotations

import os


def get_bucket_names() -> tuple[str, str]:
    """Get S3 bucket names from environment variables.

    Bucket derivation matches catalog/config.py:
    - raw_bucket = f"{project_name.replace('_', '-')}-raw"
    - curated_bucket = f"{project_name.replace('_', '-')}-curated"

    Returns:
        Tuple of (raw_bucket, curated_bucket).
    """
    project_name = os.environ["PROJECT_NAME"]
    raw_bucket = f"{project_name.replace('_', '-')}-raw"
    curated_bucket = f"{project_name.replace('_', '-')}-curated"
    return raw_bucket, curated_bucket


def apply_s3a_config(spark: "SparkSession") -> None:
    """Apply S3A configuration to Spark session.

    Args:
        spark: Active PySpark SparkSession.
    """
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
