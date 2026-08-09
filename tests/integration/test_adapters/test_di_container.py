"""Integration tests for the DI container.

These tests verify the DIContainer factory pattern and glue adapter wiring.
They use mocks for Spark/AWS dependencies to keep tests fast and isolated.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from jobs.csv_to_parquet.infrastructure.di import DIContainer, get_container


# ---------------------------------------------------------------------------
# Mock types for factory testing
# ---------------------------------------------------------------------------
class ServiceInterface:
    """Example interface for testing factory registration."""

    pass


class ServiceImpl(ServiceInterface):
    """Concrete implementation for testing."""

    pass


# ---------------------------------------------------------------------------
# Test: get_container returns DIContainer instance
# ---------------------------------------------------------------------------
def test_get_container_returns_container_instance() -> None:
    """get_container() returns a DIContainer instance."""
    container = get_container()
    assert isinstance(container, DIContainer)


def test_get_container_returns_singleton() -> None:
    """get_container() returns the same instance on successive calls."""
    container1 = get_container()
    container2 = get_container()
    assert container1 is container2


# ---------------------------------------------------------------------------
# Test: container can register and retrieve arbitrary factories
# ---------------------------------------------------------------------------
def test_container_register_and_get() -> None:
    """Container can register a factory and retrieve an instance."""
    container = DIContainer()
    container.register(ServiceInterface, lambda: ServiceImpl())

    instance = container.get(ServiceInterface)
    assert isinstance(instance, ServiceImpl)


def test_container_returns_cached_instance() -> None:
    """Container caches instances; subsequent get() returns the same object."""
    container = DIContainer()
    container.register(ServiceInterface, lambda: ServiceImpl())

    instance1 = container.get(ServiceInterface)
    instance2 = container.get(ServiceInterface)
    assert instance1 is instance2


def test_container_register_multiple_interfaces() -> None:
    """Container supports multiple registered interfaces independently."""
    container = DIContainer()

    class Interface1:
        pass

    class Interface2:
        pass

    class Impl1:
        pass

    class Impl2:
        pass

    container.register(Interface1, lambda: Impl1())
    container.register(Interface2, lambda: Impl2())

    assert isinstance(container.get(Interface1), Impl1)
    assert isinstance(container.get(Interface2), Impl2)


# ---------------------------------------------------------------------------
# Test: unregistered interface raises ValueError
# ---------------------------------------------------------------------------
def test_container_unregistered_interface_raises_valueerror() -> None:
    """Getting an unregistered interface raises ValueError with a helpful message."""

    class UnknownInterface:
        pass

    container = DIContainer()
    with pytest.raises(ValueError, match="No factory registered for"):
        container.get(UnknownInterface)


# ---------------------------------------------------------------------------
# Test: get_glue_adapter returns GlueAdapter instance
# ---------------------------------------------------------------------------
def test_get_glue_adapter_returns_glue_adapter_instance() -> None:
    """get_glue_adapter(spark, logger) returns a GlueAdapter instance."""
    container = get_container()

    # Mock Spark session and logger
    mock_spark = MagicMock(name="spark_session")
    mock_logger = MagicMock(name="logger")

    # get_glue_adapter constructs the adapter directly without registry
    adapter = container.get_glue_adapter(mock_spark, mock_logger)

    # Verify it's a GlueAdapter instance
    from jobs.csv_to_parquet.adapters.primary.glue_adapter import GlueAdapter

    assert isinstance(adapter, GlueAdapter)


def test_get_glue_adapter_receives_spark_and_logger() -> None:
    """get_glue_adapter passes spark and logger to GlueAdapter constructor."""
    container = get_container()

    mock_spark = MagicMock(name="spark_session")
    mock_logger = MagicMock(name="logger")

    adapter = container.get_glue_adapter(mock_spark, mock_logger)

    # Verify the adapter received the mocks via private attributes
    assert adapter._spark is mock_spark
    assert adapter._logger is mock_logger
