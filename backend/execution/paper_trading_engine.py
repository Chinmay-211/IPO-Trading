from datetime import datetime
from typing import Any

from backend.execution.strategy_executor import StrategyExecutor


class PaperTradingEngine:
    """
    Coordinates a strategy decision with paper execution.

    Flow:

        strategy decision
              ↓
        PaperTradingEngine
              ↓
        StrategyExecutor
              ↓
        PaperBroker

    This class contains orchestration only.
    It does not implement the IPO strategy itself.
    """

    def __init__(self, executor: StrategyExecutor):
        if executor is None:
            raise ValueError("executor is required.")

        self.executor = executor

    def execute(
        self,
        decision: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a strategy decision in paper trading.

        Expected decision format:

            {
                "action": "BUY",
                "symbol": "ABC",
                "quantity": 10,
                "price": 100.0
            }

        Supported actions:

            BUY
            SELL
            NO_TRADE

        NO_TRADE does not reach the broker.
        """

        if not isinstance(decision, dict):
            raise ValueError("decision must be a dictionary.")

        action = decision.get("action")

        if not isinstance(action, str):
            raise ValueError("decision action is required.")

        action = action.strip().upper()

        if action == "NO_TRADE":
            return {
                "action": "NO_TRADE",
                "executed": False,
                "order": None,
                "reason": decision.get(
                    "reason",
                    "Strategy returned NO_TRADE.",
                ),
            }

        if action not in {"BUY", "SELL"}:
            raise ValueError(
                f"Unsupported strategy action: {action}"
            )

        symbol = decision.get("symbol")
        quantity = decision.get("quantity")
        price = decision.get("price")

        if action == "BUY":
            result = self.executor.execute_entry(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )
        else:
            result = self.executor.execute_exit(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )

        return {
            "action": action,
            "executed": True,
            "order": result["order"],
            "symbol": result["symbol"],
            "quantity": result["quantity"],
            "price": result["price"],
            "timestamp": result["timestamp"],
        }

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the current paper position."""

        return self.executor.broker.get_position(symbol)

    def get_orders(self) -> list[dict[str, Any]]:
        """Return all paper orders."""

        return self.executor.broker.get_orders()

    def get_realized_pnl(self) -> float:
        """Return realized paper-trading P&L."""

        return self.executor.broker.get_realized_pnl()

    def reset(self) -> None:
        """Reset the paper-trading state."""

        self.executor.broker.reset()