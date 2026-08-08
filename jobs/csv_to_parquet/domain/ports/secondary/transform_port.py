"""TransformPort - Secondary port for data transformation.

This port defines the interface for data transformations.
"""

from abc import ABC, abstractmethod


class TransformPort(ABC):
    """Secondary port for data transformation.

    Driven adapters (e.g., SparkAdapter) implement this port
    to provide transformation capabilities.
    """

    @abstractmethod
    def add_city_key(self, data: list[dict]) -> list[dict]:
        """Add cidade_key column by normalizing cidade names.

        Args:
            data: List of dictionaries with cidade column.

        Returns:
            Same data with cidade_key column added.
        """
        ...

    @abstractmethod
    def derive_temp_media(self, data: list[dict]) -> list[dict]:
        """Add temp_media column as average of temp_min and temp_max.

        Args:
            data: List of dictionaries with temp_min and temp_max columns.

        Returns:
            Same data with temp_media column added.
        """
        ...
