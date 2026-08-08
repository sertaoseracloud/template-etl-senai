"""JobPort - Primary port for job execution.

This port defines the interface for the job entrypoint.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.entities import JobResult
    from application.dto import JobRequest


class JobPort(ABC):
    """Primary port for job execution.

    Driving adapter (e.g., GlueAdapter) implements this port
    to expose the job to the outside world.
    """

    @abstractmethod
    def run(self, request: "JobRequest") -> "JobResult":
        """Execute the job with the given request.

        Args:
            request: Job request with parameters.

        Returns:
            Job result with status and metrics.
        """
        ...
