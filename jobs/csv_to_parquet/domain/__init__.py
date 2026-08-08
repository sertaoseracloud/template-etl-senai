"""Hexagonal domain layer for csv_to_parquet job.

This package contains pure domain logic with no external dependencies
(pyspark, awsglue, boto3).

Architecture:
- entities: Core business objects
- value_objects: Immutable values
- ports: Interfaces (ABC) for adapters
- services: Pure business logic
"""

from domain.entities import CsvRecord, JobResult, JobStatus
from domain.value_objects import CityKey, FileInfo, Temperature
from domain.ports.primary.job_port import JobPort
from domain.ports.secondary.storage_port import StoragePort
from domain.ports.secondary.transform_port import TransformPort

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
