from datetime import datetime
from typing import Any

from backend.execution.strategy_executor import StrategyExecutor


class LivePaperTradingService:
    """
    Coordinates live market candles with paper execution.

    This service NEVER sends real orders.
    It only uses the configured StrategyExecutor,
    which can be backed by PaperBroker.
    """

    def __init__(
        self,
        strategy_executor: StrategyExecutor,
    ):
        if strategy_executor is None:
            raise ValueError(
                "strategy_executor is required."
            )

        self.strategy_executor = strategy_executor

    def enter(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a paper BUY entry.
        """

        return self.strategy_executor.execute_entry(
            symbol=symbol,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
        )

    def exit(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a paper SELL exit.
        """

        return self.strategy_executor.execute_exit(
            symbol=symbol,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
        )

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the current paper position."""

        return self.strategy_executor.broker.get_position(
            symbol
        )

    def get_orders(self) -> list[dict[str, Any]]:
        """Return paper order history."""

        return self.strategy_executor.broker.get_orders()

    def get_realized_pnl(self) -> float:
        """Return realized paper P&L."""

        return (
            self.strategy_executor
            .broker
            .get_realized_pnl()
        )

    def reset(self) -> None:
        """Reset paper-trading state."""

        self.strategy_executor.broker.reset()