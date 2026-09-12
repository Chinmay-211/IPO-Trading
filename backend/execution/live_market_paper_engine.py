from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor


class LiveMarketPaperEngine:
    """
    Processes live market ticks/candles using paper execution.

    This class NEVER places real broker orders.

    Flow:

        Live market data
              ↓
        Strategy decision
              ↓
        Paper execution
              ↓
        Paper position / P&L
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
    ):
        if initial_cash <= 0:
            raise ValueError(
                "initial_cash must be greater than zero."
            )

        self.broker = PaperBroker(
            initial_cash=initial_cash
        )

        self.strategy_executor = StrategyExecutor(
            self.broker
        )

        self.positions: dict[str, dict[str, Any]] = {}

    def execute_decision(
        self,
        decision: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a strategy-approved paper decision.

        Supported actions:

            BUY
            SELL
            NO_TRADE
        """

        if not isinstance(decision, dict):
            raise ValueError(
                "decision must be a dictionary."
            )

        action = str(
            decision.get("action", "NO_TRADE")
        ).upper()

        if action == "NO_TRADE":
            return {
                "action": "NO_TRADE",
                "executed": False,
                "symbol": decision.get("symbol"),
                "quantity": decision.get("quantity"),
                "price": decision.get("price"),
                "timestamp": timestamp,
                "order": None,
                "reason": decision.get(
                    "reason",
                    "No trade decision.",
                ),
            }

        if action not in {"BUY", "SELL"}:
            raise ValueError(
                f"Unsupported trading action: {action}"
            )

        symbol = decision.get("symbol")
        quantity = decision.get("quantity")
        price = decision.get("price")

        if not symbol:
            raise ValueError("symbol is required.")

        if quantity is None:
            raise ValueError("quantity is required.")

        if price is None:
            raise ValueError("price is required.")

        quantity = int(quantity)
        price = float(price)

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        if price <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        if action == "BUY":
            order = self.strategy_executor.execute_entry(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )

        else:
            order = self.strategy_executor.execute_exit(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )

        return {
            "action": action,
            "executed": True,
            "symbol": symbol.strip().upper(),
            "quantity": quantity,
            "price": price,
            "timestamp": timestamp,
            "order": order,
            "reason": decision.get("reason"),
        }

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        return self.broker.get_position(symbol)

    def get_orders(self) -> list[dict[str, Any]]:
        return self.broker.get_orders()

    def get_realized_pnl(self) -> float:
        return self.broker.get_realized_pnl()

    def reset(self) -> None:
        self.broker.reset()
        self.positions.clear()