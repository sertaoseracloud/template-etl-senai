"""Real PySpark integration tests for transform functions.

These tests exercise the transform module with real Spark DataFrames,
verifying schema, column lineage, and transformation correctness.
Requires a Spark session (session-scoped fixture from conftest.py).

These tests are skipped when Spark is unavailable (e.g., Java version mismatch).
"""

from __future__ import annotations

import pytest
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

# Import transforms from the canonical single-import point
from transforms import add_city_key, derive_temp_media, normalize_city_key

# Skip marker for tests requiring Spark runtime
pytestmark = pytest.mark.spark


# ---------------------------------------------------------------------------
# normalize_city_key tests (pure function, no Spark needed)
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
def test_normalize_city_key_real_data(cidade: str, expected: str) -> None:
    """normalize_city_key correctly normalizes all six dataset cities."""
    result = normalize_city_key(cidade)
    assert result == expected


def test_normalize_city_key_all_cities_known_dataset() -> None:
    """All cities in the sample dataset normalise correctly."""
    cities = {
        "Florianópolis": "florianopolis",
        "Joinville": "joinville",
        "Blumenau": "blumenau",
        "Chapecó": "chapeco",
        "Lages": "lages",
        "Criciúma": "criciuma",
    }
    for cidade, expected in cities.items():
        assert normalize_city_key(cidade) == expected


# ---------------------------------------------------------------------------
# derive_temp_media tests (real Spark DataFrame operations)
# ---------------------------------------------------------------------------
def test_derive_temp_media_real_spark_calculation(spark_session) -> None:
    """derive_temp_media computes (temp_min + temp_max) / 2 correctly."""
    df = spark_session.createDataFrame(
        [
            ("Florianopolis", "2026-01-15", 20.0, 30.0),
            ("Joinville", "2026-01-15", 21.0, 31.0),
            ("Blumenau", "2026-01-15", 18.5, 28.5),
        ],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = derive_temp_media(df)

    # Verify temp_media values are correct
    rows = result.select("cidade", "temp_media").collect()
    values = {row["cidade"]: row["temp_media"] for row in rows}
    assert values["Florianopolis"] == 25.0
    assert values["Joinville"] == 26.0
    assert values["Blumenau"] == 23.5


def test_derive_temp_media_schema(spark_session) -> None:
    """derive_temp_media adds temp_media column with DoubleType."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = derive_temp_media(df)

    # Verify schema has temp_media as DoubleType
    schema = result.schema
    temp_media_field = schema["temp_media"]
    assert temp_media_field.dataType == DoubleType()


def test_derive_temp_media_preserves_all_columns(spark_session) -> None:
    """derive_temp_media preserves all original columns."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = derive_temp_media(df)

    expected_columns = {"cidade", "data_medicao", "temp_min", "temp_max", "temp_media"}
    assert set(result.columns) == expected_columns


def test_derive_temp_media_returns_new_dataframe(spark_session) -> None:
    """derive_temp_media returns a new DataFrame, not the input."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = derive_temp_media(df)

    assert result is not df
    assert "temp_media" not in df.columns
    assert "temp_media" in result.columns


# ---------------------------------------------------------------------------
# add_city_key tests (real Spark DataFrame operations)
# ---------------------------------------------------------------------------
def test_add_city_key_real_spark(spark_session) -> None:
    """add_city_key adds cidade_key column with normalized city names."""
    df = spark_session.createDataFrame(
        [
            ("Florianopolis", "2026-01-15", 20.0, 30.0),
            ("Joinville", "2026-01-15", 21.0, 31.0),
            ("Blumenau", "2026-01-15", 18.5, 28.5),
        ],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = add_city_key(df)

    rows = result.select("cidade", "cidade_key").collect()
    values = {row["cidade"]: row["cidade_key"] for row in rows}
    assert values["Florianopolis"] == "florianopolis"
    assert values["Joinville"] == "joinville"
    assert values["Blumenau"] == "blumenau"


def test_add_city_key_schema(spark_session) -> None:
    """add_city_key adds cidade_key column with StringType."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = add_city_key(df)

    schema = result.schema
    cidade_key_field = schema["cidade_key"]
    assert cidade_key_field.dataType == StringType()


def test_add_city_key_preserves_cidade_column(spark_session) -> None:
    """add_city_key preserves the original cidade column unchanged."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = add_city_key(df)

    # cidade column should still exist with original value
    assert "cidade" in result.columns
    cidade_value = result.select("cidade").first()["cidade"]
    assert cidade_value == "Florianopolis"


def test_add_city_key_returns_new_dataframe(spark_session) -> None:
    """add_city_key returns a new DataFrame, not the input."""
    df = spark_session.createDataFrame(
        [("Florianopolis", "2026-01-15", 20.0, 30.0)],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )
    result = add_city_key(df)

    assert result is not df
    assert "cidade_key" not in df.columns
    assert "cidade_key" in result.columns


# ---------------------------------------------------------------------------
# Full pipeline tests
# ---------------------------------------------------------------------------
def test_full_transform_pipeline_schema(spark_session) -> None:
    """Full pipeline produces expected schema with all derived columns."""
    df = spark_session.createDataFrame(
        [
            ("Florianopolis", "2026-01-15", 20.0, 30.0),
            ("Joinville", "2026-01-16", 21.0, 31.0),
            ("Blumenau", "2026-01-17", 18.5, 28.5),
        ],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )

    # Apply full pipeline: derive_temp_media -> add_city_key
    with_media = derive_temp_media(df)
    with_city_key = add_city_key(with_media)

    expected_schema = StructType(
        [
            StructField("cidade", StringType(), True),
            StructField("data_medicao", StringType(), True),
            StructField("temp_min", DoubleType(), True),
            StructField("temp_max", DoubleType(), True),
            StructField("temp_media", DoubleType(), True),
            StructField("cidade_key", StringType(), True),
        ]
    )

    assert with_city_key.schema == expected_schema


def test_full_transform_pipeline_row_count(spark_session) -> None:
    """Full pipeline preserves all rows from input DataFrame."""
    df = spark_session.createDataFrame(
        [
            ("Florianopolis", "2026-01-15", 20.0, 30.0),
            ("Joinville", "2026-01-16", 21.0, 31.0),
            ("Blumenau", "2026-01-17", 18.5, 28.5),
        ],
        ["cidade", "data_medicao", "temp_min", "temp_max"],
    )

    with_media = derive_temp_media(df)
    with_city_key = add_city_key(with_media)

    assert with_city_key.count() == 3
