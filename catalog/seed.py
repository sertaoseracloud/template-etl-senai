"""Bucket creation and sample CSV upload into the emulated S3.

Runs inside the `tools` service, alongside `catalog/bootstrap.py`. Creates
the raw and curated buckets (D-09: `seed` remains separately callable from
`bootstrap`, so a schema change and a data reseed stay two distinct
commands) and uploads the three committed synthetic CSVs from
`data/sample/` to a flat `temperaturas/` prefix in the raw bucket.

The upload prefix is flat, not Hive-style (`data_medicao=.../`): each CSV
already carries `data_medicao` as a real column, and putting the date in the
S3 key as well would give the Phase 2 Spark job two conflicting sources for
the same value. The raw side stays flat; the curated side (registered by
`catalog/bootstrap.py`) is Hive-partitioned, and the Phase 2 job is what
moves between the two.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running this file as `python catalog/seed.py` (the exact invocation
# run.sh uses) puts the script's own directory on sys.path[0], not the
# repository root - see the identical comment in catalog/bootstrap.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog import config  # noqa: E402

SAMPLE_DIR = "data/sample"
RAW_PREFIX = "temperaturas/"


def ensure_bucket(s3, name: str) -> str:
    """Create the bucket, or do nothing if it already exists.

    Passes only the `Bucket` argument: an explicit bucket-location
    constraint is rejected for us-east-1 by real AWS, and the template must
    stay valid against both the emulator and real AWS. Returns "created" or
    "present".
    """
    try:
        s3.create_bucket(Bucket=name)
        return "created"
    except s3.exceptions.ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            return "present"
        raise


def upload_samples(s3, bucket: str, local_dir: str, prefix: str) -> int:
    """Upload every *.csv under local_dir to {prefix}{filename} in bucket.

    Returns the count uploaded. Raises when local_dir contains no CSV
    rather than reporting a silent success on an empty upload.
    """
    csv_paths = sorted(Path(local_dir).glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No *.csv files found under '{local_dir}'.")

    for csv_path in csv_paths:
        s3.upload_file(str(csv_path), bucket, f"{prefix}{csv_path.name}")

    return len(csv_paths)


def main() -> int:
    s3 = config.s3_client()
    raw = config.raw_bucket()
    curated = config.curated_bucket()

    raw_result = ensure_bucket(s3, raw)
    print(f"[ok] raw bucket '{raw}': {raw_result}")

    # Created empty so the Phase 2 job has somewhere to write.
    curated_result = ensure_bucket(s3, curated)
    print(f"[ok] curated bucket '{curated}': {curated_result}")

    count = upload_samples(s3, raw, SAMPLE_DIR, RAW_PREFIX)
    print(f"[ok] uploaded {count} sample CSV(s) to s3://{raw}/{RAW_PREFIX}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
