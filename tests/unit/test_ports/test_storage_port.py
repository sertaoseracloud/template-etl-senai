"""Unit tests for domain ports (contract tests)."""

from __future__ import annotations

from unittest.mock import MagicMock

from jobs.csv_to_parquet.adapters.secondary.spark_adapter import SparkAdapter
from jobs.csv_to_parquet.domain.ports.secondary.storage_port import StoragePort
from jobs.csv_to_parquet.domain.ports.secondary.transform_port import TransformPort


class TestStoragePortContract:
    """Test StoragePort contract implementation."""

    def test_spark_adapter_implements_storage_port(self) -> None:
        """SparkAdapter implements StoragePort."""
        mock_spark = MagicMock()
        adapter = SparkAdapter(mock_spark)
        assert isinstance(adapter, StoragePort)

    def test_storage_port_requires_read_csv(self) -> None:
        """StoragePort defines read_csv method."""
        assert hasattr(StoragePort, "read_csv")
        assert callable(getattr(StoragePort, "read_csv"))

    def test_storage_port_requires_write_parquet(self) -> None:
        """StoragePort defines write_parquet method."""
        assert hasattr(StoragePort, "write_parquet")
        assert callable(getattr(StoragePort, "write_parquet"))

    def test_storage_port_requires_get_file_info(self) -> None:
        """StoragePort defines get_file_info method."""
        assert hasattr(StoragePort, "get_file_info")
        assert callable(getattr(StoragePort, "get_file_info"))


class TestTransformPortContract:
    """Test TransformPort contract implementation."""

    def test_spark_adapter_implements_transform_port(self) -> None:
        """SparkAdapter implements TransformPort."""
        mock_spark = MagicMock()
        adapter = SparkAdapter(mock_spark)
        assert isinstance(adapter, TransformPort)

    def test_transform_port_requires_add_city_key(self) -> None:
        """TransformPort defines add_city_key method."""
        assert hasattr(TransformPort, "add_city_key")
        assert callable(getattr(TransformPort, "add_city_key"))

    def test_transform_port_requires_derive_temp_media(self) -> None:
        """TransformPort defines derive_temp_media method."""
        assert hasattr(TransformPort, "derive_temp_media")
        assert callable(getattr(TransformPort, "derive_temp_media"))


class TestSparkAdapterWithMocks:
    """Test SparkAdapter using mocks."""

    def test_add_city_key(self) -> None:
        """add_city_key normalizes city names."""
        mock_spark = MagicMock()
        adapter = SparkAdapter(mock_spark)
        data = [
            {"cidade": "Florianópolis", "temp_min": 20.0, "temp_max": 30.0},
            {"cidade": "Joinville", "temp_min": 21.0, "temp_max": 31.0},
        ]
        result = adapter.add_city_key(data)
        assert result[0]["cidade_key"] == "florianopolis"
        assert result[1]["cidade_key"] == "joinville"
        # Original unchanged
        assert "cidade_key" not in data[0]

    def test_derive_temp_media(self) -> None:
        """derive_temp_media calculates average temperature."""
        mock_spark = MagicMock()
        adapter = SparkAdapter(mock_spark)
        data = [
            {"cidade": "Blumenau", "temp_min": 15.0, "temp_max": 25.0},
            {"cidade": "Chapecó", "temp_min": 10.0, "temp_max": 20.0},
        ]
        result = adapter.derive_temp_media(data)
        assert result[0]["temp_media"] == 20.0
        assert result[1]["temp_media"] == 15.0
        # Original unchanged
        assert "temp_media" not in data[0]
