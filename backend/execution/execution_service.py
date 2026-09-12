from datetime import datetime
from typing import Any

from backend.execution.broker import Broker


class ExecutionService:
    """
    Coordinates strategy-generated orders with a broker.

    The service does not contain trading strategy logic.
    It only validates and forwards execution requests to the
    configured broker.
    """

    def __init__(self, broker: Broker):
        if broker is None:
            raise ValueError("broker is required.")

        self.broker = broker

    def buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute a BUY order through the configured broker."""

        return self.broker.place_order(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=price,
            timestamp=timestamp,
        )

    def sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute a SELL order through the configured broker."""

        return self.broker.place_order(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            price=price,
            timestamp=timestamp,
        )

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the broker's current position."""

        return self.broker.get_position(symbol)

    def get_orders(self) -> list[dict[str, Any]]:
        """Return broker order history."""

        return self.broker.get_orders()

    def get_realized_pnl(self) -> float:
        """Return realized P&L from the broker."""

        return self.broker.get_realized_pnl()

    def reset(self) -> None:
        """Reset the underlying broker state."""

        self.broker.reset()