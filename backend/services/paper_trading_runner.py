from datetime import datetime
from typing import Any

from backend.execution.paper_broker import PaperBroker
from backend.execution.paper_trading_engine import PaperTradingEngine
from backend.execution.strategy_executor import StrategyExecutor


class PaperTradingRunner:
    """
    Runs a strategy decision through the paper-trading stack.

    Flow:

        Strategy Decision
              ↓
        PaperTradingRunner
              ↓
        PaperTradingEngine
              ↓
        StrategyExecutor
              ↓
        PaperBroker

    No real broker or exchange is contacted.
    """

    def __init__(
        self,
        engine: PaperTradingEngine | None = None,
    ):
        if engine is None:
            broker = PaperBroker(initial_cash=100000)
            executor = StrategyExecutor(broker)
            engine = PaperTradingEngine(executor)

        self.engine = engine

    def run_one(
        self,
        decision: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute one strategy decision in paper trading.

        Supported decisions:

            BUY
            SELL
            NO_TRADE
        """

        if not isinstance(decision, dict):
            raise ValueError(
                "decision must be a dictionary."
            )

        result = self.engine.execute(
            decision=decision,
            timestamp=timestamp,
        )

        return {
            "action": result["action"],
            "executed": result["executed"],
            "symbol": result.get("symbol"),
            "quantity": result.get("quantity"),
            "price": result.get("price"),
            "timestamp": result.get("timestamp"),
            "order": result.get("order"),
            "reason": result.get("reason"),
        }

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