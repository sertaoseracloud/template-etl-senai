"""Hexagonal domain layer for csv_to_parquet job.

This package contains pure domain logic with no external dependencies
(pyspark, awsglue, boto3).

Architecture:
- entities: Core business objects
- value_objects: Immutable values
- ports: Interfaces (ABC) for adapters
- services: Pure business logic
"""

from jobs.csv_to_parquet.domain.entities import CsvRecord, JobResult, JobStatus
from jobs.csv_to_parquet.domain.ports.primary.job_port import JobPort
from jobs.csv_to_parquet.domain.ports.secondary.storage_port import StoragePort
from jobs.csv_to_parquet.domain.ports.secondary.transform_port import TransformPort
from jobs.csv_to_parquet.domain.value_objects import CityKey, FileInfo, Temperature

__all__ = [
    # entities
    "CsvRecord",
    "JobResult",
    "JobStatus",
    # value_objects
    "CityKey",
    "FileInfo",
    "Temperature",
    # ports
    "JobPort",
    "StoragePort",
    "TransformPort",
]
