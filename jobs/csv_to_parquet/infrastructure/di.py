"""Dependency Injection container for csv_to_parquet job.

Provides factory-based DI for hexagonal architecture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

    from jobs.csv_to_parquet.adapters.primary.glue_adapter import GlueAdapter
    from jobs.csv_to_parquet.adapters.secondary.spark_adapter import SparkAdapter
    from jobs.csv_to_parquet.application.use_cases import ProcessCsvUseCase

T = TypeVar("T")


class DIContainer:
    """Simple dependency injection container using factory pattern."""

    def __init__(self) -> None:
        """Initialize container."""
        self._factories: dict[type, callable] = {}
        self._instances: dict[type, object] = {}

    def register(self, interface: type[T], factory: callable[[], T]) -> None:
        """Register a factory for an interface.

        Args:
            interface: Interface/class type.
            factory: Factory function to create instance.
        """
        self._factories[interface] = factory

    def get(self, interface: type[T]) -> T:
        """Get an instance for an interface.

        Args:
            interface: Interface/class type.

        Returns:
            Instance (cached or newly created).
        """
        if interface not in self._instances:
            if interface not in self._factories:
                raise ValueError(f"No factory registered for {interface}")
            self._instances[interface] = self._factories[interface]()
        return self._instances[interface]

    def get_glue_adapter(
        self, spark: "SparkSession", logger: object
    ) -> "GlueAdapter":
        """Get GlueAdapter instance.

        Args:
            spark: Active PySpark session.
            logger: Glue logger instance.

        Returns:
            Configured GlueAdapter.
        """
        from jobs.csv_to_parquet.adapters.primary.glue_adapter import GlueAdapter
        from jobs.csv_to_parquet.application.use_cases import ProcessCsvUseCase
        from jobs.csv_to_parquet.adapters.secondary.spark_adapter import SparkAdapter

        storage = SparkAdapter(spark)
        transformer = SparkAdapter(spark)
        use_case = ProcessCsvUseCase(storage, transformer)
        return GlueAdapter(spark, use_case, logger)


# Global container instance
_container: DIContainer | None = None


def get_container() -> DIContainer:
    """Get or create the global DI container."""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container
