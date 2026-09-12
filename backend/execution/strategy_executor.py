from datetime import datetime
from typing import Any

from backend.execution.broker import Broker


class StrategyExecutor:
    """
    Executes trading decisions through a Broker.

    The executor is broker-agnostic and works with PaperBroker
    without exposing broker-specific implementation details.
    """

    def __init__(self, broker: Broker):
        if broker is None:
            raise ValueError("broker is required.")

        self.broker = broker

    def execute_entry(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute a BUY entry."""

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if isinstance(quantity, bool) or not isinstance(
            quantity,
            int,
        ):
            raise ValueError(
                "quantity must be an integer."
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        try:
            normalized_price = float(price)
        except (TypeError, ValueError):
            raise ValueError(
                "price must be numeric."
            ) from None

        if normalized_price <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        if timestamp is not None and not isinstance(
            timestamp,
            datetime,
        ):
            raise ValueError(
                "timestamp must be a datetime."
            )

        order = self.broker.place_order(
            symbol=symbol.strip(),
            side="BUY",
            quantity=quantity,
            price=normalized_price,
            timestamp=timestamp,
        )

        return {
            "action": "BUY",
            "symbol": symbol.strip().upper(),
            "quantity": quantity,
            "price": normalized_price,
            "timestamp": (
                order["timestamp"]
                if timestamp is None
                else timestamp
            ),
            "order": order,
        }

    def execute_exit(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute a SELL exit."""

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if isinstance(quantity, bool) or not isinstance(
            quantity,
            int,
        ):
            raise ValueError(
                "quantity must be an integer."
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        try:
            normalized_price = float(price)
        except (TypeError, ValueError):
            raise ValueError(
                "price must be numeric."
            ) from None

        if normalized_price <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        if timestamp is not None and not isinstance(
            timestamp,
            datetime,
        ):
            raise ValueError(
                "timestamp must be a datetime."
            )

        order = self.broker.place_order(
            symbol=symbol.strip(),
            side="SELL",
            quantity=quantity,
            price=normalized_price,
            timestamp=timestamp,
        )

        return {
            "action": "SELL",
            "symbol": symbol.strip().upper(),
            "quantity": quantity,
            "price": normalized_price,
            "timestamp": (
                order["timestamp"]
                if timestamp is None
                else timestamp
            ),
            "order": order,
        }