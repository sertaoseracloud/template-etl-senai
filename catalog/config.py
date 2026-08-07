"""Single configuration seam for every resource name and every boto3 client.

Every resource name derives from the single `PROJECT_NAME` environment
variable through exactly two `str.replace` calls, and Phase 3's Terraform
must reproduce the same two calls to stay in sync with this module:

    raw_bucket()      = f"{PROJECT_NAME.replace('_', '-')}-raw"
    curated_bucket()  = f"{PROJECT_NAME.replace('_', '-')}-curated"
    database_name()   = f"{PROJECT_NAME.replace('-', '_')}_db"

The underscore-to-hyphen transform is required because S3 bucket names
forbid underscores. The hyphen-to-underscore transform is required because
a Glue database name containing a hyphen must be quoted in every Athena
query. There is exactly one derivation site: this module. No other file in
this repository re-derives a resource name.

Every boto3 client built here is constructed with an explicit
`endpoint_url` read from `AWS_ENDPOINT_URL`. Construction raises a named
error when that variable is unset or empty, so a client can never fall
through to real AWS regional endpoint resolution.

Nothing in this module imports Spark or PySpark, and nothing under
`catalog/` should. The Phase 2 Spark job declares its own schema and does
not read `catalog/schema/*.json` (D-04) — `transforms/` stays pure and free
of file I/O so it remains unit-testable without Glue or AWS.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import boto3


def project_name() -> str:
    """Return PROJECT_NAME from the environment.

    Raises RuntimeError naming the variable when it is unset or empty.
    """
    value = os.environ.get("PROJECT_NAME", "")
    if not value:
        raise RuntimeError("PROJECT_NAME is missing or empty in the environment.")
    return value


def raw_bucket() -> str:
    """Return the raw-zone bucket name derived from PROJECT_NAME."""
    return f"{project_name().replace('_', '-')}-raw"


def curated_bucket() -> str:
    """Return the curated-zone bucket name derived from PROJECT_NAME."""
    return f"{project_name().replace('_', '-')}-curated"


def database_name() -> str:
    """Return the Glue database name derived from PROJECT_NAME."""
    return f"{project_name().replace('-', '_')}_db"


def endpoint_url() -> str:
    """Return AWS_ENDPOINT_URL from the environment.

    Raises RuntimeError naming the variable when it is unset or empty. An
    empty endpoint would make boto3 fall through to real AWS regional
    endpoint resolution, which is exactly the accident this raise prevents
    (T-01-03).
    """
    value = os.environ.get("AWS_ENDPOINT_URL", "")
    if not value:
        raise RuntimeError("AWS_ENDPOINT_URL is missing or empty in the environment.")
    return value


def glue_client():
    """Return a boto3 Glue client bound to the explicit emulator endpoint."""
    return boto3.client("glue", endpoint_url=endpoint_url())


def s3_client():
    """Return a boto3 S3 client bound to the explicit emulator endpoint."""
    return boto3.client("s3", endpoint_url=endpoint_url())


def load_schema(path: str) -> dict:
    """Open `path` read-only and return `json.load` of it.

    Read mode only: nothing in this repository writes the schema file at
    runtime, which is what makes concurrent consumers safe.
    """
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)
