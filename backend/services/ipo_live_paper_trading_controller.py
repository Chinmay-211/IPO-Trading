from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor


class IPOLivePaperTradingController:
    """
    Controls one live IPO paper trade.

    Market data:
        Angel One WebSocket
            ↓
        1-minute candles
            ↓
        this controller

    Execution:
        Strategy-approved action
            ↓
        StrategyExecutor
            ↓
        PaperBroker

    This class NEVER places a real order.
    """

    def __init__(
        self,
        broker: PaperBroker | None = None,
    ):
        self.broker = (
            broker
            if broker is not None
            else PaperBroker(initial_cash=100000)
        )

        self.executor = StrategyExecutor(
            self.broker
        )

        self.symbol: str | None = None
        self.quantity: int | None = None

        self.entry_price: float | None = None
        self.target_price: float | None = None
        self.stop_loss_price: float | None = None

        self.entry_order: dict[str, Any] | None = None
        self.exit_order: dict[str, Any] | None = None

        self.status = "IDLE"
        self.exit_reason: str | None = None

    def start_trade(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Start a paper trade after the strategy has approved entry.
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        entry_price = float(entry_price)
        target_price = float(target_price)
        stop_loss_price = float(stop_loss_price)

        if entry_price <= 0:
            raise ValueError(
                "entry_price must be greater than zero."
            )

        if target_price <= entry_price:
            raise ValueError(
                "target_price must be greater than entry_price."
            )

        if stop_loss_price >= entry_price:
            raise ValueError(
                "stop_loss_price must be below entry_price."
            )

        if self.status not in {"IDLE", "CLOSED"}:
            raise RuntimeError(
                "A paper trade is already active."
            )

        self.symbol = symbol.strip().upper()
        self.quantity = quantity
        self.entry_price = entry_price
        self.target_price = target_price
        self.stop_loss_price = stop_loss_price

        self.entry_order = self.executor.execute_entry(
            symbol=self.symbol,
            quantity=quantity,
            price=entry_price,
            timestamp=timestamp,
        )

        self.exit_order = None
        self.exit_reason = None
        self.status = "OPEN"

        return {
            "status": self.status,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss_price": self.stop_loss_price,
            "entry_order": self.entry_order,
        }

    def process_candle(
        self,
        candle: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process one live 1-minute candle.

        Conservative rule:
            If both stop-loss and target are touched
            in the same candle, STOP-LOSS wins.
        """

        if self.status != "OPEN":
            return self._state()

        if not isinstance(candle, dict):
            raise ValueError(
                "candle must be a dictionary."
            )

        try:
            high = float(candle["high"])
            low = float(candle["low"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "candle must contain valid high and low values."
            )

        timestamp = candle.get("timestamp")

        if low <= self.stop_loss_price:
            return self._close_trade(
                price=self.stop_loss_price,
                reason="STOP_LOSS",
                timestamp=timestamp,
            )

        if high >= self.target_price:
            return self._close_trade(
                price=self.target_price,
                reason="TARGET",
                timestamp=timestamp,
            )

        return self._state()

    def _close_trade(
        self,
        price: float,
        reason: str,
        timestamp: Any = None,
    ) -> dict[str, Any]:
        """
        Close the active paper position.
        """

        if self.status != "OPEN":
            return self._state()

        self.exit_order = self.executor.execute_exit(
            symbol=self.symbol,
            quantity=self.quantity,
            price=float(price),
            timestamp=timestamp,
        )

        pnl = (
            float(price) - self.entry_price
        ) * self.quantity

        pnl_percent = (
            (
                float(price) - self.entry_price
            )
            / self.entry_price
        ) * 100

        self.exit_reason = reason
        self.status = "CLOSED"

        return {
            "status": self.status,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": float(price),
            "target_price": self.target_price,
            "stop_loss_price": self.stop_loss_price,
            "exit_reason": reason,
            "entry_order": self.entry_order,
            "exit_order": self.exit_order,
            "profit_loss": pnl,
            "profit_loss_percent": pnl_percent,
            "timestamp": timestamp,
        }

    def _state(self) -> dict[str, Any]:
        """
        Return current trade state.
        """

        return {
            "status": self.status,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss_price": self.stop_loss_price,
            "exit_reason": self.exit_reason,
            "entry_order": self.entry_order,
            "exit_order": self.exit_order,
        }

    def get_position(
        self,
    ) -> dict[str, Any] | None:
        if self.symbol is None:
            return None

        return self.broker.get_position(
            self.symbol
        )

    def get_orders(self) -> list[dict[str, Any]]:
        return self.broker.get_orders()

    def get_realized_pnl(self) -> float:
        return self.broker.get_realized_pnl()

    def reset(self) -> None:
        self.broker.reset()

        self.symbol = None
        self.quantity = None

        self.entry_price = None
        self.target_price = None
        self.stop_loss_price = None

        self.entry_order = None
        self.exit_order = None

        self.exit_reason = None
        self.status = "IDLE"