"""Data Transfer Objects for the csv_to_parquet job."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JobRequest:
    """Request object for job execution."""

    job_name: str
    file_key: Optional[str] = None
    raw_bucket: str = ""
    curated_bucket: str = ""
    partition_cols: list[str] = field(default_factory=lambda: ["data_medicao", "cidade_key"])

    def __post_init__(self) -> None:
        """Validate request."""
        if not self.job_name:
            raise ValueError("job_name is required")


@dataclass
class JobResponse:
    """Response object for job execution."""

    success: bool
    rows_read: int = 0
    rows_written: int = 0
    input_path: str = ""
    output_path: str = ""
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "rows_read": self.rows_read,
            "rows_written": self.rows_written,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "message": self.message,
            "error": self.error,
        }
