"""Secondary ports (driven adapters).

These ports define the interfaces that driven adapters must implement.
"""

from domain.ports.secondary.storage_port import StoragePort
from domain.ports.secondary.transform_port import TransformPort

__all__ = ["StoragePort", "TransformPort"]
