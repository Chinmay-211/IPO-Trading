from datetime import datetime
from typing import Any

from backend.execution.broker import Broker
from backend.execution.execution_service import ExecutionService
from backend.execution.live_broker import LiveBroker
from backend.execution.strategy_executor import StrategyExecutor


class LiveTradingController:
    """
    Coordinates an IPO trading decision with order execution.

    This controller does NOT implement the trading strategy itself.
    The strategy/backtest layer determines whether an entry or exit
    should happen.

    PaperBroker is allowed during validation.

    LiveBroker remains blocked because real broker integration has
    not yet been implemented.
    """

    def __init__(
        self,
        broker: Broker,
        live_enabled: bool = False,
    ):
        if broker is None:
            raise ValueError(
                "broker is required."
            )

        if not isinstance(live_enabled, bool):
            raise ValueError(
                "live_enabled must be a boolean."
            )

        self.broker = broker
        self.live_enabled = live_enabled

        self.execution_service = ExecutionService(
            broker
        )

        self.strategy_executor = StrategyExecutor(
            broker
        )

    def execute_entry(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a strategy-approved BUY entry.
        """

        self._check_execution_allowed()

        return self.strategy_executor.execute_entry(
            symbol=symbol,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
        )

    def execute_exit(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a strategy-approved SELL exit.
        """

        self._check_execution_allowed()

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
        """Return the current broker position."""

        return self.execution_service.get_position(
            symbol
        )

    def get_orders(self) -> list[dict[str, Any]]:
        """Return execution history."""

        return self.execution_service.get_orders()

    def get_realized_pnl(self) -> float:
        """Return realized broker P&L."""

        return self.execution_service.get_realized_pnl()

    def reset(self) -> None:
        """Reset broker execution state."""

        self.execution_service.reset()

    def _check_execution_allowed(self) -> None:
        """
        Enforce the execution safety boundary.

        1. Controller disabled:
           execution is rejected.

        2. LiveBroker:
           real execution is not implemented yet.

        3. PaperBroker:
           execution is allowed for paper trading.
        """

        if not self.live_enabled:
            return

        if isinstance(self.broker, LiveBroker):
            raise RuntimeError(
                "Live trading is not enabled. "
                "Live broker integration is not implemented yet."
            )