"""S3 polling utilities for local event-driven ETL simulation.

Provides watch_loop() and trigger_job() functions that poll the emulated S3 bucket
for new files and trigger the Glue job with --file-key parameter. This simulates
EventBridge S3 ObjectCreated triggers locally.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# Running this file from docker compose uses /workspace as working dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog import config

# Poll interval in seconds (D-04: default 5 seconds)
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
PROCESSED_FILE = "/tmp/processed_files.txt"


def load_processed_files() -> set[str]:
    """Load the set of already-processed file keys.

    Returns:
        Set of S3 keys that have already been processed.
    """
    if not Path(PROCESSED_FILE).exists():
        return set()
    with open(PROCESSED_FILE, "r") as f:
        return {line.strip() for line in f if line.strip()}


def save_processed_file(key: str) -> None:
    """Record a file key as processed.

    Args:
        key: The S3 key of the file that was processed.
    """
    with open(PROCESSED_FILE, "a") as f:
        f.write(f"{key}\n")


def poll_and_trigger() -> list[str]:
    """Poll S3 for new files and trigger the job for each new file.

    Returns:
        List of new file keys that were triggered.
    """
    s3 = config.s3_client()
    bucket = config.raw_bucket()
    prefix = "temperaturas/"

    processed = load_processed_files()
    triggered = []

    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        contents = response.get("Contents", [])

        for obj in contents:
            key = obj["Key"]
            # Skip directories and already-processed files
            if key in processed or key.endswith("/"):
                continue
            print(f"New file detected: s3://{bucket}/{key}")
            trigger_job(key)
            save_processed_file(key)
            triggered.append(key)
    except Exception as e:
        print(f"Error polling S3: {e}", file=sys.stderr)
        raise

    return triggered


def trigger_job(file_key: str) -> None:
    """Trigger the Glue job with --file-key parameter.

    Args:
        file_key: The S3 key of the file to process.

    Note:
        Uses list-based subprocess args to avoid command injection (T-05-03).
    """
    cmd = [
        "docker", "compose", "--profile", "glue", "run", "--rm", "glue",
        "spark-submit", "jobs/csv_to_parquet/job.py",
        "--JOB_NAME", "csv_to_parquet",
        "--file-key", file_key
    ]
    print(f"Triggering job: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Job failed: {result.stderr}", file=sys.stderr)
    else:
        print(f"Job completed successfully")


def watch_loop() -> None:
    """Infinite polling loop that watches for new S3 files.

    Runs until Ctrl+C is pressed. Each poll interval, checks for new files
    in the temperaturas/ prefix and triggers the job for each new file.
    """
    print(f"Starting S3 watch loop (poll interval: {POLL_INTERVAL}s)")
    print("Press Ctrl+C to exit")
    try:
        while True:
            triggered = poll_and_trigger()
            if triggered:
                print(f"Triggered {len(triggered)} job(s)")
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nWatch loop stopped")


if __name__ == "__main__":
    watch_loop()
