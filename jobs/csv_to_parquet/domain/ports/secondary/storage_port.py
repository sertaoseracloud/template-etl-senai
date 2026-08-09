"""StoragePort - Secondary port for data storage operations.

This port defines the interface for reading and writing data.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.value_objects import FileInfo


class StoragePort(ABC):
    """Secondary port for storage operations.

    Driven adapters (e.g., S3Adapter, SparkAdapter) implement this port
    to provide data storage capabilities.
    """

    @abstractmethod
    def read_csv(self, path: str) -> list[dict]:
        """Read CSV data from the given path.

        Args:
            path: S3 or local path to CSV file.

        Returns:
            List of dictionaries representing CSV rows.
        """
        ...

    @abstractmethod
    def write_parquet(
        self, data: list[dict], path: str, partition_cols: list[str]
    ) -> None:
        """Write data to Parquet format at the given path.

        Args:
            data: List of dictionaries to write.
            path: S3 or local output path.
            partition_cols: Columns to partition by.
        """
        ...

    @abstractmethod
    def get_file_info(self, path: str) -> "FileInfo | None":
        """Get file information.

        Args:
            path: S3 or local path.

        Returns:
            FileInfo if file exists, None otherwise.
        """
        ...
