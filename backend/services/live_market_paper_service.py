from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.execution.live_market_paper_engine import (
    LiveMarketPaperEngine,
)


class LiveMarketPaperService:
    """
    High-level service for live-market paper trading.

    Market data may come from Angel One WebSocket,
    but execution is ALWAYS through PaperBroker.
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
    ):
        self.engine = LiveMarketPaperEngine(
            initial_cash=initial_cash
        )

    def process_decision(
        self,
        decision: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        return self.engine.execute_decision(
            decision=decision,
            timestamp=timestamp,
        )

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        return self.engine.get_position(symbol)

    def get_orders(self) -> list[dict[str, Any]]:
        return self.engine.get_orders()

    def get_realized_pnl(self) -> float:
        return self.engine.get_realized_pnl()

    def reset(self) -> None:
        self.engine.reset()