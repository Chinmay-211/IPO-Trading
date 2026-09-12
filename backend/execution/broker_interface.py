from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BrokerInterface(Protocol):
    """
    Standardized broker interface protocol for Indian IPO trading.

    Both PaperBroker and future Live Broker adapters (Angel One / Zerodha Kite)
    must satisfy this protocol.
    """

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Place an order and return its execution details."""
        ...

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the current position for a symbol."""
        ...

    def get_orders(self) -> list[dict[str, Any]]:
        """Return all recorded orders."""
        ...

    def get_realized_pnl(self) -> float:
        """Return total realized P&L."""
        ...

    def reset(self) -> None:
        """Reset internal positions, orders, and P&L state."""
        ...
