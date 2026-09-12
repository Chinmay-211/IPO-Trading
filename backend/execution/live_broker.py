from datetime import datetime
from typing import Any

from backend.execution.broker import Broker


class LiveBroker(Broker):
    """
    Live-broker execution boundary.

    Real-money execution is deliberately disabled at this stage.

    The enabled flag is retained as an explicit safety boundary.
    Even when enabled=True, actual broker integration is not yet
    implemented, so order execution remains blocked.
    """

    def __init__(self, enabled: bool = False):
        if not isinstance(enabled, bool):
            raise ValueError(
                "enabled must be a boolean."
            )

        self.enabled = enabled
        self.orders: list[dict[str, Any]] = []

    def _ensure_enabled(self) -> None:
        """Reject access when live trading is disabled."""

        if not self.enabled:
            raise RuntimeError(
                "Live trading is disabled. "
                "Enable it explicitly before placing real orders."
            )

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Place a live order.

        Actual broker integration is not implemented yet.
        """

        self._ensure_enabled()

        raise NotImplementedError(
            "Live broker order execution is not implemented yet."
        )

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve a live broker position.

        Actual broker integration is not implemented yet.
        """

        self._ensure_enabled()

        raise NotImplementedError(
            "Live broker position retrieval is not implemented yet."
        )

    def get_orders(self) -> list[dict[str, Any]]:
        """
        Return locally recorded live orders.

        Currently empty because real execution is not implemented.
        """

        return list(self.orders)

    def get_realized_pnl(self) -> float:
        """
        Retrieve live realized P&L.

        Actual broker integration is not implemented yet.
        """

        self._ensure_enabled()

        raise NotImplementedError(
            "Live broker P&L retrieval is not implemented yet."
        )

    def reset(self) -> None:
        """Clear locally recorded orders."""

        self.orders.clear()