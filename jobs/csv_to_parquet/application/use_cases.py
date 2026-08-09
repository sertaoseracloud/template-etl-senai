"""Use cases for the csv_to_parquet job.

Pure application logic orchestrating ports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.ports.secondary.storage_port import StoragePort
    from domain.ports.secondary.transform_port import TransformPort

from jobs.csv_to_parquet.application.dto import JobRequest, JobResponse


class ProcessCsvUseCase:
    """Use case for processing CSV to Parquet."""

    def __init__(
        self,
        storage: StoragePort,
        transformer: TransformPort,
    ) -> None:
        """Initialize with storage and transformer ports."""
        self._storage = storage
        self._transformer = transformer

    def execute(self, request: JobRequest) -> JobResponse:
        """Execute the CSV to Parquet process.

        Args:
            request: Job request with parameters.

        Returns:
            Job response with results.
        """
        # Initialize input_path before try block to avoid fragile locals() workaround
        input_path = ""
        try:
            # Determine input path
            if request.file_key:
                input_path = f"s3://{request.raw_bucket}/{request.file_key}"
            else:
                input_path = f"s3://{request.raw_bucket}/temperaturas/"

            # Read CSV
            data = self._storage.read_csv(input_path)
            rows_read = len(data)

            if rows_read == 0:
                return _empty_response(request, "No data to process")

            # Transform
            data = self._transformer.add_city_key(data)
            data = self._transformer.derive_temp_media(data)

            # Write Parquet
            # Distinguish event-driven output path from batch processing
            if request.file_key:
                output_path = f"s3://{request.curated_bucket}/temperaturas/{request.file_key.rsplit('.', 1)[0]}/"
            else:
                output_path = f"s3://{request.curated_bucket}/temperaturas/"
            self._storage.write_parquet(data, output_path, request.partition_cols)

            return JobResponse(
                success=True,
                rows_read=rows_read,
                rows_written=len(data),
                input_path=input_path,
                output_path=output_path,
                message="CSV processed successfully",
            )

        except FileNotFoundError as e:
            return JobResponse(
                success=False,
                input_path=input_path,
                message="File not found",
                error=str(e),
            )
        except Exception as e:
            return JobResponse(
                success=False,
                input_path=input_path,
                message="Processing failed",
                error=str(e),
            )


def _empty_response(request: JobRequest, message: str) -> JobResponse:
    """Create response for empty data case."""
    return JobResponse(
        success=True,
        rows_read=0,
        rows_written=0,
        input_path=f"s3://{request.raw_bucket}/temperaturas/",
        output_path=f"s3://{request.curated_bucket}/temperaturas/",
        message=message,
    )
