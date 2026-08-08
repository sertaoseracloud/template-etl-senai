"""Value objects for the csv_to_parquet job.

Value objects are immutable and can be compared by value.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class CityKey:
    """A normalized, partition-safe city identifier."""

    value: str

    @classmethod
    def from_cidade(cls, cidade: str) -> CityKey:
        """Create from a cidade name, normalizing it.

        Applies NFKD normalization, removes combining characters,
        and lowercases the result.
        """
        nfkd = unicodedata.normalize("NFKD", cidade)
        normalized = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
        return cls(value=normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Temperature:
    """Temperature values with min/max validation."""

    min_temp: float
    max_temp: float

    @property
    def media(self) -> float:
        """Calculate average temperature."""
        return (self.min_temp + self.max_temp) / 2

    def __post_init__(self) -> None:
        """Validate temperature values."""
        if self.min_temp > self.max_temp:
            raise ValueError(f"min_temp ({self.min_temp}) cannot exceed max_temp ({self.max_temp})")


@dataclass(frozen=True)
class FileInfo:
    """Information about an S3 file."""

    key: str
    size_bytes: int
    path: str
