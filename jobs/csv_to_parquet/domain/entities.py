"""Core entities for the csv_to_parquet job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class JobStatus(Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CsvRecord:
    """A single CSV record representing a temperature measurement."""

    cidade: str
    data_medicao: str
    temp_min: float
    temp_max: float
    cidade_key: str | None = None
    temp_media: float | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cidade": self.cidade,
            "data_medicao": self.data_medicao,
            "temp_min": self.temp_min,
            "temp_max": self.temp_max,
            "cidade_key": self.cidade_key,
            "temp_media": self.temp_media,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CsvRecord:
        """Create from dictionary."""
        return cls(
            cidade=str(data["cidade"]),
            data_medicao=str(data["data_medicao"]),
            temp_min=float(data["temp_min"]),
            temp_max=float(data["temp_max"]),
            cidade_key=data.get("cidade_key"),
            temp_media=float(data["temp_media"]) if data.get("temp_media") else None,
        )


@dataclass
class JobResult:
    """Result of a job execution."""

    status: JobStatus
    rows_read: int = 0
    rows_written: int = 0
    input_path: str = ""
    output_path: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    file_key: str | None = None
    file_size_bytes: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "status": self.status.value,
            "rows_read": self.rows_read,
            "rows_written": self.rows_written,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "file_key": self.file_key,
            "file_size_bytes": self.file_size_bytes,
            "error": self.error_message,
        }
