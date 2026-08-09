"""S3 upload utilities for local event-driven ETL simulation.

Provides upload_file() function that uploads files to the emulated S3 bucket
under the temperaturas/ prefix, following the same pattern as catalog/seed.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running this file from docker compose uses /workspace as working dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog import config

RAW_PREFIX = "temperaturas/"


def upload_file(local_path: str) -> str:
    """Upload a file to S3 under the temperaturas/ prefix.

    Args:
        local_path: Path to the local file to upload.

    Returns:
        The S3 key (temperaturas/{filename}) of the uploaded file.

    Raises:
        FileNotFoundError: If the local file does not exist.
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {local_path}")

    bucket = config.raw_bucket()
    s3_key = f"{RAW_PREFIX}{local_path.name}"

    s3 = config.s3_client()
    s3.upload_file(str(local_path), bucket, s3_key)

    print(s3_key)
    return s3_key


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m tools.s3_upload <local_file>", file=sys.stderr)
        sys.exit(1)
    upload_file(sys.argv[1])
