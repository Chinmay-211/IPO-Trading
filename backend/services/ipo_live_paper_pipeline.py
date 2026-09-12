from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.services.ipo_live_listing_strategy_controller import (
    IPOLiveListingStrategyController,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)


class IPOLivePaperPipeline:
    """
    End-to-end live IPO listing-day paper-trading pipeline.

    Flow:

        completed 1-minute candle
                    ↓
        live listing strategy
                    ↓
              BUY / SELL
                    ↓
        paper execution service
                    ↓
                PaperBroker

    This pipeline NEVER places real broker orders.
    """

    def __init__(
        self,
        strategy_controller: IPOLiveListingStrategyController,
        execution_service: IPOLivePaperExecutionService,
    ):
        if strategy_controller is None:
            raise ValueError(
                "strategy_controller is required."
            )

        if not isinstance(
            strategy_controller,
            IPOLiveListingStrategyController,
        ):
            raise TypeError(
                "strategy_controller must be an "
                "IPOLiveListingStrategyController."
            )

        if execution_service is None:
            raise ValueError(
                "execution_service is required."
            )

        if not isinstance(
            execution_service,
            IPOLivePaperExecutionService,
        ):
            raise TypeError(
                "execution_service must be an "
                "IPOLivePaperExecutionService."
            )

        self.strategy_controller = strategy_controller
        self.execution_service = execution_service

        self.decisions: list[dict[str, Any]] = []
        self.executions: list[dict[str, Any]] = []

    def process_candle(
        self,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Process one completed live candle.

        Returns None when the strategy has no decision.

        When a decision occurs, the strategy decision and
        paper execution result are returned together.
        """

        decision = (
            self.strategy_controller.process_candle(
                candle
            )
        )

        if decision is None:
            return None

        self.decisions.append(decision)

        timestamp = decision.get("timestamp")

        execution = (
            self.execution_service.execute_decision(
                decision=decision,
                timestamp=timestamp,
            )
        )

        self.executions.append(execution)

        return {
            "decision": decision,
            "execution": execution,
        }

    def process_candles(
        self,
        candles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Process completed candles sequentially.

        Only candles that generate strategy decisions
        produce entries in the returned list.
        """

        results: list[dict[str, Any]] = []

        for candle in candles:
            result = self.process_candle(candle)

            if result is not None:
                results.append(result)

        return results

    def get_position(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Return the current paper position.
        """

        if symbol is None:
            symbol = self.strategy_controller.symbol

        return self.execution_service.get_position(
            symbol
        )

    def get_orders(self) -> list[dict[str, Any]]:
        """Return paper order history."""

        return self.execution_service.get_orders()

    def get_realized_pnl(self) -> float:
        """Return realized paper P&L."""

        return self.execution_service.get_realized_pnl()

    def get_state(self) -> dict[str, Any]:
        """
        Return combined strategy and execution state.
        """

        return {
            "strategy": (
                self.strategy_controller.get_state()
            ),
            "orders": self.get_orders(),
            "realized_pnl": self.get_realized_pnl(),
            "decisions": len(self.decisions),
            "executions": len(self.executions),
        }

    def reset(self) -> None:
        """
        Reset both strategy and paper execution state.
        """

        self.strategy_controller.reset()
        self.execution_service.reset()

        self.decisions.clear()
        self.executions.clear()