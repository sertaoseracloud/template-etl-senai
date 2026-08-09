"""Primary ports (driving adapters).

These ports define the interfaces that driving adapters must implement.
"""

from jobs.csv_to_parquet.domain.ports.primary.job_port import JobPort

__all__ = ["JobPort"]
