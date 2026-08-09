"""GlueAdapter - Primary adapter for Glue job execution.

This adapter wraps the Glue job entrypoint and orchestrates the use case.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

from application.dto import JobRequest
from application.use_cases import ProcessCsvUseCase
from domain.entities import JobResult, JobStatus
from domain.ports.primary.job_port import JobPort


class GlueAdapter(JobPort):
    """Primary adapter for AWS Glue job execution."""

    def __init__(
        self,
        spark: SparkSession,
        use_case: ProcessCsvUseCase,
        logger: object | None = None,
    ) -> None:
        """Initialize with Spark and use case.

        Args:
            spark: Active PySpark session.
            use_case: ProcessCsvUseCase instance.
            logger: Optional Glue logger.
        """
        self._spark = spark
        self._use_case = use_case
        self._logger = logger

    def run(self, request: JobRequest) -> JobResult:
        """Execute the job.

        Args:
            request: Job request parameters.

        Returns:
            Job result with status and metrics.
        """
        started_at = datetime.now(UTC)
        result = self._use_case.execute(request)

        # Log CloudWatch-compatible event
        if self._logger:
            iso_timestamp = datetime.now(UTC).isoformat()
            self._logger.info(
                f"TRIGGER_EVENT: {{"
                f"'file_key': '{request.file_key or 'batch'}', "
                f"'size_bytes': {0}, "
                f"'timestamp': '{iso_timestamp}'"
                f"}}"
            )

        return JobResult(
            status=JobStatus.COMPLETED if result.success else JobStatus.FAILED,
            rows_read=result.rows_read,
            rows_written=result.rows_written,
            input_path=result.input_path,
            output_path=result.output_path,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            error_message=result.error,
            file_key=request.file_key,
        )
