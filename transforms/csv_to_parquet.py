"""Pure transformation logic for the csv_to_parquet job.

This module contains only Python stdlib and pyspark.sql. It must NOT import
any package that requires AWS credentials. The D-08 invariant test in
tests/conftest.py enforces this at test-collection time.

No S3A committer is explicitly configured here. The options are:

- Magic committer (fs.s3a.committer.name=magic):
  NOT used. Floci v1.5.11 does not correctly persist ObjectParts metadata
  after CompleteMultipartUpload (floci-io/floci#30), which breaks the Magic
  committer's task-enumeration step. This is a known Floci gap, not a
  configuration problem.

- Directory staging committer (fs.s3a.committer.name=directory):
  NOT used. Adds staging-then-upload overhead that yields zero benefit for
  18-kilobyte Parquet files across 18 partitions. Append conflict mode is
  tolerated but not optimized for.

- Default FileOutputCommitter (what you get with no configuration):
  USED. Direct PutObject to the final path. No multipart, no staging, no
  rename. Failed tasks leave partial files at their final paths; the
  integration test's content assertion (D-04) is the safety net.

If this job is migrated to real AWS S3, re-evaluate the Magic committer:
real S3 has no GetObjectAttributes gap and multipart upload is beneficial
for files larger than ~100 MB.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from pyspark.sql import DataFrame
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


def normalize_city_key(cidade: str) -> str:
    """Normalize a city name into a partition-safe key.

    Applies, in order:
      1. NFKD decomposition to split accented characters into base letter +
         combining diacritical mark;
      2. Removal of all combining characters (accents, tildes, cedillas, …);
      3. Lowercasing.

    The cidade column itself is preserved unchanged in the DataFrame; this
    function produces the derived ``cidade_key`` partition column.

    Examples::

        >>> normalize_city_key("Florianópolis")
        'florianopolis'
        >>> normalize_city_key("Chapecó")
        'chapeco'
        >>> normalize_city_key("Criciúma")
        'criciuma'
        >>> normalize_city_key("Joinville")
        'joinville'
        >>> normalize_city_key("Blumenau")
        'blumenau'
    """
    nfkd = unicodedata.normalize("NFKD", cidade)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Registered once at module level so add_city_key reuses the same UDF object.
_normalize_udf = udf(normalize_city_key, StringType())


def read_csv(spark: SparkSession, path: str) -> DataFrame:
    """Read a CSV file into a PySpark DataFrame.

    Parameters
    ----------
    spark
        Active SparkSession.
    path
        S3A or local path to the CSV file.

    Returns
    -------
    DataFrame
        Columns: cidade, data_medicao, temp_min, temp_max.
        Schema is inferred from the CSV header and content.
    """
    return spark.read.csv(path, header=True, inferSchema=True)


def derive_temp_media(df: DataFrame) -> DataFrame:
    """Derive the ``temp_media`` column as the arithmetic mean of temp_min and temp_max.

    Parameters
    ----------
    df
        Input DataFrame that must contain ``temp_min`` and ``temp_max`` columns.

    Returns
    -------
    DataFrame
        New DataFrame with a ``temp_media`` column added. The original
        columns are preserved unchanged. This function never mutates the
        input DataFrame.
    """
    return df.withColumn("temp_media", (df.temp_min + df.temp_max) / 2)


def add_city_key(df: DataFrame) -> DataFrame:
    """Add a ``cidade_key`` column by normalising the ``cidade`` column.

    The ``cidade`` column is preserved unchanged. ``cidade_key`` holds the
    lowercase, accent-free form that serves as a partition key alongside
    ``data_medicao`` (compound partitioning: data_medicao × cidade_key =
    3 dates × 6 cities = 18 partitions).

    Parameters
    ----------
    df
        Input DataFrame that must contain a ``cidade`` column.

    Returns
    -------
    DataFrame
        New DataFrame with a ``cidade_key`` column added.
    """
    return df.withColumn("cidade_key", _normalize_udf(df.cidade))


def write_parquet(df: DataFrame, path: str, partition_cols: list[str]) -> None:
    """Write a DataFrame to Parquet, partitioned by the given columns.

    Uses append mode (D-04): new data is added to existing data in the
    output prefix. The default FileOutputCommitter is used — see the module
    docstring for the rationale.

    Parameters
    ----------
    df
        DataFrame to write.
    path
        S3A or local output path.
    partition_cols
        Column names to partition by, in order. Compound partitioning is
        supported; e.g. ``["data_medicao", "cidade_key"]`` produces one
        Parquet file per (date, city) pair.
    """
    df.write.mode("overwrite").partitionBy(*partition_cols).parquet(path)
