"""Integration test configuration.

Registers custom markers for tests.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "spark: tests that require a running Spark session with Java 17+",
    )
    config.addinivalue_line(
        "markers",
        "glue: tests that require Glue container with S3A support",
    )
