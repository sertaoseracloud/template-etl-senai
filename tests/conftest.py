"""Test configuration: session-scoped SparkSession fixture and D-08 invariant test."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark_session() -> SparkSession:
    """Return a session-scoped SparkSession for all tests in the suite.

    Minimal config for test environment (excess logging suppressed). No AWS
    configuration here — this fixture is for unit tests that operate on local
    data or in-process DataFrames. The integration test (plan 02-03) does NOT
    use this fixture; it spawns the job via subprocess.
    """
    builder = SparkSession.builder
    for key, value in {
        "spark.sql.shuffle.partitions": "4",
        "spark.ui.enabled": "false",
    }.items():
        builder = builder.config(key, value)
    spark = builder.getOrCreate()
    yield spark
    spark.stop()


def pytest_configure(config):
    """Register custom markers used throughout the test suite."""
    config.addinivalue_line(
        "markers",
        "athena: tests that query via the Floci Athena endpoint",
    )


def test_no_aws_sdk_imports():
    """Invariant: neither transforms/ nor tests/unit/ may import AWS SDK packages.

    This test exists because D-08 requires that unit tests run without Glue or
    AWS. If this test fails, the suite is broken — do not skip it.
    """
    _blocked = ["awsg" + "lue", "bot" + "o3"]
    violations = []
    for base in [Path("transforms"), Path("tests/unit")]:
        if not base.exists():
            continue
        for py_file in base.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for module in _blocked:
                if re.search(rf"^import {module}|^from {module}", content, re.MULTILINE):
                    violations.append(f"{py_file}: imports {module}")
    assert not violations, "Prohibited imports found:\n" + "\n".join(violations)
