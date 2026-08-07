"""Unit tests for the transforms module.

All tests run without Glue, without AWS, and without the integration test's
subprocess infrastructure. They use the spark_session fixture from
conftest.py.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from pyspark.sql import DataFrame

from tests.conftest import spark_session
from transforms import (
    add_city_key,
    derive_temp_media,
    normalize_city_key,
    read_csv,
    write_parquet,
)


# ---------------------------------------------------------------------------
# normalize_city_key tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "cidade,expected",
    [
        ("Florianópolis", "florianopolis"),
        ("Joinville", "joinville"),
        ("Blumenau", "blumenau"),
        ("Chapecó", "chapeco"),
        ("Lages", "lages"),
        ("Criciúma", "criciuma"),
    ],
)
def test_normalize_city_key_all_six_cities(cidade: str, expected: str) -> None:
    """All six cities in the sample dataset normalise correctly."""
    assert normalize_city_key(cidade) == expected


def test_normalize_city_key_florianopolis() -> None:
    assert normalize_city_key("Florianópolis") == "florianopolis"


def test_normalize_city_key_chapeco() -> None:
    assert normalize_city_key("Chapecó") == "chapeco"


def test_normalize_city_key_criciuma() -> None:
    assert normalize_city_key("Criciúma") == "criciuma"


def test_normalize_city_key_no_accent() -> None:
    assert normalize_city_key("Joinville") == "joinville"
    assert normalize_city_key("Blumenau") == "blumenau"


# ---------------------------------------------------------------------------
# derive_temp_media tests
# ---------------------------------------------------------------------------

def test_derive_temp_media(spark_session: pytest.fixture) -> None:
    """temp_media equals (temp_min + temp_max) / 2 for every row."""
    df = spark_session.createDataFrame(
        [
            ("Florianopolis", "2026-01-15", 20.0, 30.0),
            ("Joinville", "2026-01-15", 21.0, 31.0),
        ],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = derive_temp_media(df)
    rows = result.select("temp_media").collect()
    assert rows[0]["temp_media"] == 25.0
    assert rows[1]["temp_media"] == 26.0


def test_derive_temp_media_preserves_original_columns(
    spark_session: pytest.fixture,
) -> None:
    """Original temp_min and temp_max columns remain unchanged."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = derive_temp_media(df)
    assert "temp_media" in result.columns
    assert "temp_min" in result.columns
    assert "temp_max" in result.columns
    assert "cidade" in result.columns


def test_derive_temp_media_does_not_mutate_input(
    spark_session: pytest.fixture,
) -> None:
    """derive_temp_media returns a new DataFrame; the input is unchanged."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = derive_temp_media(df)
    assert result is not df
    assert "temp_media" not in df.columns
    assert "temp_media" in result.columns


# ---------------------------------------------------------------------------
# add_city_key tests
# ---------------------------------------------------------------------------

def test_add_city_key(spark_session: pytest.fixture) -> None:
    """cidade_key column exists and holds normalised city keys; cidade unchanged."""
    df = spark_session.createDataFrame(
        [
            ("Florianopolis", "2026-01-15", 20.0, 30.0),
            ("Joinville", "2026-01-15", 21.0, 31.0),
        ],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = add_city_key(df)
    assert "cidade_key" in result.columns
    rows = result.select("cidade", "cidade_key").collect()
    assert rows[0]["cidade_key"] == "florianopolis"
    assert rows[1]["cidade_key"] == "joinville"
    # cidade column preserved unchanged
    assert rows[0]["cidade"] == "Florianopolis"


def test_add_city_key_does_not_mutate_input(spark_session: pytest.fixture) -> None:
    """add_city_key returns a new DataFrame; the input has no cidade_key column."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = add_city_key(df)
    assert result is not df
    assert "cidade_key" not in df.columns
    assert "cidade_key" in result.columns


# ---------------------------------------------------------------------------
# read_csv tests
# ---------------------------------------------------------------------------

def test_read_csv_with_header_and_schema_inference(
    spark_session: pytest.fixture,
) -> None:
    """read_csv produces a DataFrame with the expected columns and inferred types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test_data.csv")
        with open(csv_path, "w", encoding="utf-8") as fh:
            fh.write("cidade,data_medicao,temp_min,temp_max\n")
            fh.write("Florianopolis,2026-01-15,20.0,30.0\n")
            fh.write("Joinville,2026-01-15,21.0,31.0\n")
        df = read_csv(spark_session, csv_path)
        assert list(df.columns) == ["cidade", "data_medicao", "temp_min", "temp_max"]
        assert df.count() == 2


# ---------------------------------------------------------------------------
# write_parquet tests
# ---------------------------------------------------------------------------

def test_write_parquet_produces_output(spark_session: pytest.fixture) -> None:
    """write_parquet creates Parquet files in the output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        df = spark_session.createDataFrame(
            [
                ("Florianopolis", "2026-01-15", 20.0, 30.0),
                ("Joinville", "2026-01-15", 21.0, 31.0),
            ],
            ["cidade", "data_medicao", "temp_min", "temp_max"],
        )
        output_path = os.path.join(tmpdir, "output")
        write_parquet(df, output_path, partition_cols=["cidade"])
        # Read back and confirm data is present
        result = spark_session.read.parquet(output_path)
        assert result.count() == 2
