from abc import ABC, abstractmethod
from typing import Any


class IPODataSource(ABC):
    """Interface that every IPO data source must implement."""

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw IPO records from the external source."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a raw source record into our standard format."""
        raise NotImplementedError