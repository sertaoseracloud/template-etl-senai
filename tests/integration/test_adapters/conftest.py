"""S3 fixtures and helpers for adapter integration tests.

These fixtures use Floci (local S3 emulator) via catalog.config, which is
correct -- boto3 is available inside the Glue container and these tests
run via subprocess spark-submit same as test_job.py.
"""

from __future__ import annotations

import boto3
import pytest

from catalog.config import (  # noqa: E402  # boto3 available in Glue container
    curated_bucket,
    endpoint_url,
    s3_client,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clear_curated_prefix() -> int:
    """Delete all objects under the curated bucket's temperaturas/ prefix.

    This is the D-04 state preparation: the test controls its own preconditions
    so COUNT is deterministic regardless of how many times the job has run.
    Returns the number of objects deleted.
    """
    s3 = s3_client()
    bucket = curated_bucket()
    prefix = "temperaturas/"
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    deleted_count = 0
    for page in pages:
        if "Contents" in page:
            keys = [{"Key": obj["Key"]} for obj in page["Contents"]]
            s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            deleted_count += len(keys)
    return deleted_count


def upload_csv_to_s3(csv_content: str, key: str, bucket: str | None = None) -> None:
    """Upload CSV content to S3.

    Args:
        csv_content: CSV file content as string.
        key: S3 object key (e.g., 'temperaturas/data.csv').
        bucket: Optional bucket name. Defaults to curated bucket.
    """
    s3 = s3_client()
    target_bucket = bucket or curated_bucket()
    s3.put_object(Bucket=target_bucket, Key=key, Body=csv_content.encode("utf-8"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def s3_client_fixture():
    """Return a boto3 S3 client bound to the explicit Floci endpoint."""
    return boto3.client("s3", endpoint_url=endpoint_url())


@pytest.fixture(scope="module")
def s3_test_bucket():
    """Return the curated bucket name."""
    return curated_bucket()


@pytest.fixture(scope="function")
def clean_curated_prefix():
    """Clear the temperaturas/ prefix before each test.

    Function-scoped to ensure each test starts with a clean state.
    """
    clear_curated_prefix()
    yield
    # Optional: cleanup after test if needed
