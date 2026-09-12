from typing import Any

from backend.execution.execution_service import ExecutionService
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_trading_orchestrator import (
    IPOTradingOrchestrator,
)


class IPOPaperTradingBatch:
    """
    Runs the IPO trading strategy against stored historical candles
    using the paper broker.

    This is a batch/integration layer only.
    Strategy rules remain outside this class.
    """

    def __init__(
        self,
        orchestrator: IPOTradingOrchestrator,
    ):
        if orchestrator is None:
            raise ValueError(
                "orchestrator is required."
            )

        self.orchestrator = orchestrator

    def run_one(
        self,
        ipo: dict[str, Any],
        candles: list[dict[str, Any]],
        quantity: int,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
    ) -> dict[str, Any]:
        """
        Run paper trading for one IPO using supplied candles.
        """

        if not isinstance(ipo, dict):
            raise ValueError("ipo must be a dictionary.")

        symbol = ipo.get("symbol")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "IPO trading symbol is required."
            )

        listing_date = ipo.get("listing_date")

        if not listing_date:
            raise ValueError(
                "IPO listing_date is required."
            )

        result = self.orchestrator.execute_trade(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            candles=candles,
        )

        return {
            "ipo_id": ipo.get("id"),
            "company_name": ipo.get("company_name"),
            "symbol": symbol.strip().upper(),
            "listing_date": listing_date,
            "status": result["status"],
            "entry": result["entry"],
            "exit": result["exit"],
            "exit_reason": result["exit_reason"],
            "profit_loss": result["profit_loss"],
            "profit_loss_percent": result[
                "profit_loss_percent"
            ],
        }

    def run_batch(
        self,
        trades: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Run multiple IPO paper trades.

        Each item must contain:

            ipo
            candles
            quantity
            entry_price
            target_price
            stop_loss_price
        """

        if not isinstance(trades, list):
            raise ValueError(
                "trades must be a list."
            )

        results = []

        for trade in trades:
            if not isinstance(trade, dict):
                raise ValueError(
                    "Each trade must be a dictionary."
                )

            result = self.run_one(
                ipo=trade["ipo"],
                candles=trade["candles"],
                quantity=trade["quantity"],
                entry_price=trade["entry_price"],
                target_price=trade["target_price"],
                stop_loss_price=trade["stop_loss_price"],
            )

            results.append(result)

        return results