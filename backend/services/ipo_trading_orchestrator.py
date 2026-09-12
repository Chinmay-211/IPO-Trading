from datetime import datetime
from typing import Any

from backend.execution.execution_service import ExecutionService
from backend.execution.strategy_executor import StrategyExecutor


class IPOTradingOrchestrator:
    """
    Coordinates the complete IPO trading execution flow.

    Flow:
        strategy decision
            -> BUY entry
            -> monitor candles
            -> TARGET / STOP-LOSS exit

    The orchestrator is broker-agnostic. PaperBroker can be used
    safely for validation.
    """

    def __init__(
        self,
        execution_service: ExecutionService,
        strategy_executor: StrategyExecutor,
    ):
        if execution_service is None:
            raise ValueError(
                "execution_service is required."
            )

        if strategy_executor is None:
            raise ValueError(
                "strategy_executor is required."
            )

        self.execution_service = execution_service
        self.strategy_executor = strategy_executor

    def execute_trade(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
        candles: list[dict[str, Any]],
        entry_timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute one complete paper-trading strategy cycle.

        Entry is executed immediately at entry_price.

        Subsequent candles are examined in chronological order.

        TARGET:
            Exit when candle high reaches target.

        STOP-LOSS:
            Exit when candle low reaches stop loss.

        If neither occurs, the position remains open.
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if not isinstance(candles, list):
            raise ValueError("candles must be a list.")

        entry = self.strategy_executor.execute_entry(
            symbol=symbol,
            quantity=quantity,
            price=entry_price,
            timestamp=entry_timestamp,
        )

        normalized_symbol = symbol.strip().upper()

        result = {
            "status": "OPEN",
            "symbol": normalized_symbol,
            "quantity": quantity,
            "entry": entry,
            "exit": None,
            "exit_reason": None,
            "profit_loss": None,
            "profit_loss_percent": None,
        }

        for candle in candles:
            if not isinstance(candle, dict):
                continue

            timestamp = candle.get("timestamp")

            try:
                high = float(candle["high"])
                low = float(candle["low"])
            except (KeyError, TypeError, ValueError):
                continue

            exit_price = None
            exit_reason = None

            # Stop-loss takes priority if both levels occur
            # within the same candle.
            if low <= stop_loss_price:
                exit_price = float(stop_loss_price)
                exit_reason = "STOP_LOSS"

            elif high >= target_price:
                exit_price = float(target_price)
                exit_reason = "TARGET"

            if exit_price is None:
                continue

            exit_result = self.strategy_executor.execute_exit(
                symbol=normalized_symbol,
                quantity=quantity,
                price=exit_price,
                timestamp=timestamp,
            )

            pnl = (
                exit_price - float(entry_price)
            ) * quantity

            pnl_percent = (
                (
                    exit_price - float(entry_price)
                )
                / float(entry_price)
            ) * 100

            result.update(
                {
                    "status": "CLOSED",
                    "exit": exit_result,
                    "exit_reason": exit_reason,
                    "profit_loss": pnl,
                    "profit_loss_percent": pnl_percent,
                }
            )

            return result

        return result