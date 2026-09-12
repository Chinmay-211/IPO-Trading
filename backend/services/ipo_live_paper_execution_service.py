from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.execution.strategy_executor import StrategyExecutor
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)


class IPOLivePaperExecutionService:
    """
    Connects IPO listing-day strategy decisions to paper execution.

    Safety boundary:

        Strategy decision
            ↓
        this service
            ↓
        LivePaperTradingService
            ↓
        StrategyExecutor
            ↓
        PaperBroker

    This service NEVER uses LiveBroker.
    """

    def __init__(
        self,
        paper_service: LivePaperTradingService,
        risk_manager: Any | None = None,
        portfolio_state_fn: Any | None = None,
    ):
        if paper_service is None:
            raise ValueError(
                "paper_service is required."
            )

        if not isinstance(
            paper_service,
            LivePaperTradingService,
        ):
            raise TypeError(
                "paper_service must be a "
                "LivePaperTradingService."
            )

        self.paper_service = paper_service
        self.risk_manager = risk_manager
        self.portfolio_state_fn = portfolio_state_fn

    def execute_decision(
        self,
        decision: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute one strategy decision through paper trading.

        Supported actions:

            BUY
            SELL
            EXIT
            NO_TRADE
            HOLD
        """

        if not isinstance(decision, dict):
            raise ValueError(
                "decision must be a dictionary."
            )

        action = str(
            decision.get("action", "")
        ).strip().upper()

        symbol = decision.get("symbol")
        quantity = decision.get("quantity")
        price = decision.get("price")

        if action in {"NO_TRADE", "HOLD", ""}:
            return {
                "action": action or "NO_TRADE",
                "executed": False,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp,
                "order": None,
                "reason": decision.get(
                    "reason",
                    "No execution required.",
                ),
            }

        if action not in {"BUY", "SELL", "EXIT"}:
            return {
                "action": action,
                "executed": False,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp,
                "order": None,
                "reason": "Unsupported strategy action.",
            }

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "symbol is required for execution."
            )

        if quantity is None:
            raise ValueError(
                "quantity is required for execution."
            )

        if price is None:
            raise ValueError(
                "price is required for execution."
            )

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
            if self.risk_manager is not None:
                total_pnl = self.paper_service.get_realized_pnl()
                positions = {symbol.strip().upper(): self.paper_service.get_position(symbol)}
                if callable(self.portfolio_state_fn):
                    try:
                        total_pnl, positions = self.portfolio_state_fn()
                    except Exception:
                        pass

                allowed, reason = self.risk_manager.can_enter(
                    symbol=symbol.strip().upper(),
                    price=price,
                    quantity=quantity,
                    current_realized_pnl=total_pnl,
                    active_positions=positions,
                )
                if not allowed:
                    return {
                        "action": "BLOCKED_BY_RISK",
                        "executed": False,
                        "symbol": symbol.strip().upper(),
                        "quantity": quantity,
                        "price": price,
                        "timestamp": timestamp,
                        "order": None,
                        "reason": f"Risk limit exceeded: {reason}",
                    }

            order = self.paper_service.enter(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )
        else:
            order = self.paper_service.exit(
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
        return self.paper_service.get_position(symbol)

    def get_orders(self) -> list[dict[str, Any]]:
        return self.paper_service.get_orders()

    def get_realized_pnl(self) -> float:
        return self.paper_service.get_realized_pnl()

    def reset(self) -> None:
        self.paper_service.reset()