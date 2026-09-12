from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class Broker(ABC):
    """Common interface for paper and live order execution."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Place an order and return its execution details."""
        raise NotImplementedError

    @abstractmethod
    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the current position for a symbol."""
        raise NotImplementedError

    @abstractmethod
    def get_orders(self) -> list[dict[str, Any]]:
        """Return recorded orders."""
        raise NotImplementedError

    @abstractmethod
    def get_realized_pnl(self) -> float:
        """Return realized P&L."""
        raise NotImplementedError