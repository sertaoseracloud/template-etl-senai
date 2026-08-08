"""Adapters layer for csv_to_parquet job.

Contains primary (driving) and secondary (driven) adapters.
"""

from jobs.csv_to_parquet.adapters.primary.glue_adapter import GlueAdapter
from jobs.csv_to_parquet.adapters.secondary.spark_adapter import SparkAdapter

__all__ = ["GlueAdapter", "SparkAdapter"]
