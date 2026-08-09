"""SparkAdapter - Secondary adapter implementing StoragePort and TransformPort.

This adapter uses PySpark for data processing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

from jobs.csv_to_parquet.domain.ports.secondary.storage_port import StoragePort
from jobs.csv_to_parquet.domain.ports.secondary.transform_port import TransformPort
from jobs.csv_to_parquet.domain.value_objects import FileInfo


class SparkAdapter(StoragePort, TransformPort):
    """Adapter using PySpark for storage and transformation operations."""

    def __init__(self, spark: SparkSession) -> None:
        """Initialize with SparkSession.

        Args:
            spark: Active PySpark session.
        """
        self._spark = spark

    def read_csv(self, path: str) -> list[dict]:
        """Read CSV using PySpark and convert to list of dicts."""
        # Convert S3A path
        s3a_path = path.replace("s3://", "s3a://")
        df = self._spark.read.csv(s3a_path, header=True, inferSchema=True)
        # NOTE: df.collect() loads all data to driver memory (WR-03).
        # For large datasets this will cause OOM errors. Consider refactoring
        # transform ports to work with DataFrames instead of list[dict].
        return [row.asDict() for row in df.collect()]

    def write_parquet(self, data: list[dict], path: str, partition_cols: list[str]) -> None:
        """Write data to Parquet format."""

        s3a_path = path.replace("s3://", "s3a://")
        df = self._spark.createDataFrame(data)
        df.write.mode("overwrite").partitionBy(*partition_cols).parquet(s3a_path)

    def get_file_info(self, path: str) -> FileInfo | None:
        """Get file information using Hadoop FileSystem."""
        s3a_path = path.replace("s3://", "s3a://")
        try:
            fs = self._spark.sparkContext._jvm.org.apache.hadoop.fs.FileSystem.get(
                self._spark.sparkContext._jvm.java.net.URI.create(s3a_path),
                self._spark.sparkContext._jsc.hadoopConfiguration(),
            )
            hadoop_path = self._spark.sparkContext._jvm.org.apache.hadoop.fs.Path(s3a_path)
            if fs.exists(hadoop_path):
                status = fs.getFileStatus(hadoop_path)
                return FileInfo(
                    key=hadoop_path.getName(),
                    size_bytes=status.getLen(),
                    path=s3a_path,
                )
        except Exception as e:
            import logging

            logging.warning(f"Failed to get file info for {path}: {e}")
            return None
        return None

    def add_city_key(self, data: list[dict]) -> list[dict]:
        """Add cidade_key column by normalizing cidade names."""
        import unicodedata

        def normalize(cidade: str) -> str:
            nfkd = unicodedata.normalize("NFKD", cidade)
            return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

        result = []
        for row in data:
            new_row = dict(row)
            new_row["cidade_key"] = normalize(row["cidade"])
            result.append(new_row)
        return result

    def derive_temp_media(self, data: list[dict]) -> list[dict]:
        """Add temp_media column as average of temp_min and temp_max."""
        result = []
        for row in data:
            new_row = dict(row)
            new_row["temp_media"] = (row["temp_min"] + row["temp_max"]) / 2
            result.append(new_row)
        return result
