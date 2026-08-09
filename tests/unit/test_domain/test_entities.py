"""Unit tests for domain entities using mocks (no Spark required)."""

from __future__ import annotations

from datetime import UTC, datetime

from jobs.csv_to_parquet.domain.entities import (
    CsvRecord,
    JobResult,
    JobStatus,
)


class TestCsvRecord:
    """Test CsvRecord entity."""

    def test_to_dict(self) -> None:
        """CsvRecord converts to dict correctly."""
        record = CsvRecord(
            cidade="Florianopolis",
            data_medicao="2026-01-15",
            temp_min=20.0,
            temp_max=30.0,
            cidade_key="florianopolis",
            temp_media=25.0,
        )
        result = record.to_dict()
        assert result["cidade"] == "Florianopolis"
        assert result["data_medicao"] == "2026-01-15"
        assert result["temp_min"] == 20.0
        assert result["temp_max"] == 30.0
        assert result["cidade_key"] == "florianopolis"
        assert result["temp_media"] == 25.0

    def test_from_dict(self) -> None:
        """CsvRecord creates from dict correctly."""
        data = {
            "cidade": "Joinville",
            "data_medicao": "2026-01-16",
            "temp_min": 21.0,
            "temp_max": 31.0,
            "cidade_key": "joinville",
            "temp_media": 26.0,
        }
        record = CsvRecord.from_dict(data)
        assert record.cidade == "Joinville"
        assert record.temp_min == 21.0
        assert record.temp_max == 31.0
        assert record.cidade_key == "joinville"
        assert record.temp_media == 26.0

    def test_from_dict_without_optional_fields(self) -> None:
        """CsvRecord creates from dict without optional fields."""
        data = {
            "cidade": "Blumenau",
            "data_medicao": "2026-01-17",
            "temp_min": 18.0,
            "temp_max": 28.0,
        }
        record = CsvRecord.from_dict(data)
        assert record.cidade == "Blumenau"
        assert record.cidade_key is None
        assert record.temp_media is None


class TestJobResult:
    """Test JobResult entity."""

    def test_to_dict_completed(self) -> None:
        """JobResult with COMPLETED status converts to dict."""
        result = JobResult(
            status=JobStatus.COMPLETED,
            rows_read=100,
            rows_written=95,
            input_path="s3://bucket/input.csv",
            output_path="s3://bucket/output.parquet",
            started_at=datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 1, 15, 10, 1, 0, tzinfo=UTC),
        )
        data = result.to_dict()
        assert data["status"] == "completed"
        assert data["rows_read"] == 100
        assert data["rows_written"] == 95
        assert data["error"] is None

    def test_to_dict_failed(self) -> None:
        """JobResult with FAILED status includes error message."""
        result = JobResult(
            status=JobStatus.FAILED,
            rows_read=50,
            rows_written=0,
            error_message="File not found",
        )
        data = result.to_dict()
        assert data["status"] == "failed"
        assert data["error"] == "File not found"

    def test_job_status_enum_values(self) -> None:
        """JobStatus enum has expected values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.SKIPPED.value == "skipped"

    def test_to_dict_pending(self) -> None:
        """JobResult with PENDING status."""
        result = JobResult(status=JobStatus.PENDING)
        data = result.to_dict()
        assert data["status"] == "pending"

    def test_to_dict_failed_without_message(self) -> None:
        """JobResult with FAILED status but no error message."""
        result = JobResult(status=JobStatus.FAILED, rows_read=0, rows_written=0)
        data = result.to_dict()
        assert data["status"] == "failed"
        assert data["error"] is None
