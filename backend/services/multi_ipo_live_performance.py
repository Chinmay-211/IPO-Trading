from __future__ import annotations

from typing import Any

from backend.services.ipo_paper_performance_service import (
    IPOPaperPerformanceService,
)
from backend.services.multi_ipo_live_monitor import (
    MultiIPOLiveMonitor,
)


class MultiIPOLivePerformance:
    """
    Connects multi-IPO live paper monitoring with
    paper-trading performance reporting.

    Reporting only:
        - does not place orders
        - does not make strategy decisions
        - does not modify broker state
    """

    def __init__(
        self,
        monitor: MultiIPOLiveMonitor,
    ):
        if monitor is None:
            raise ValueError(
                "monitor is required."
            )

        if not isinstance(
            monitor,
            MultiIPOLiveMonitor,
        ):
            raise TypeError(
                "monitor must be a "
                "MultiIPOLiveMonitor."
            )

        self.monitor = monitor

    def _orders_for_symbol(
        self,
        symbol: str,
    ) -> list[dict[str, Any]]:
        symbol = symbol.strip().upper()

        state = self.monitor.get_state(symbol)

        controller = self.monitor._ipos[
            symbol
        ]["controller"]

        execution_service = getattr(
            controller,
            "execution_service",
            None,
        )

        if execution_service is not None:
            return execution_service.get_orders()

        paper_service = getattr(
            controller,
            "paper_service",
            None,
        )

        if paper_service is not None:
            return paper_service.get_orders()

        return []

    def get_symbol_report(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        symbol = symbol.strip().upper()

        if not self.monitor.contains(symbol):
            raise KeyError(
                f"IPO is not registered: {symbol}"
            )

        performance = (
            IPOPaperPerformanceService(
                self._orders_for_symbol(symbol)
            )
        )

        return performance.get_symbol_summary(
            symbol
        )

    def get_report(
        self,
    ) -> dict[str, Any]:
        """
        Return combined performance for all
        registered IPOs.
        """

        reports = {}

        for symbol in self.monitor.symbols():
            reports[symbol] = (
                self.get_symbol_report(symbol)
            )

        total_trades = sum(
            report["total_trades"]
            for report in reports.values()
        )

        winning_trades = sum(
            report["winning_trades"]
            for report in reports.values()
        )

        losing_trades = sum(
            report["losing_trades"]
            for report in reports.values()
        )

        breakeven_trades = sum(
            report["breakeven_trades"]
            for report in reports.values()
        )

        profit_loss = sum(
            report["profit_loss"]
            for report in reports.values()
        )

        invested = sum(
            self._invested_for_symbol(symbol)
            for symbol in self.monitor.symbols()
        )

        win_rate = (
            winning_trades / total_trades * 100
            if total_trades
            else 0.0
        )

        profit_loss_percent = (
            profit_loss / invested * 100
            if invested
            else 0.0
        )

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "breakeven_trades": breakeven_trades,
            "win_rate": win_rate,
            "profit_loss": profit_loss,
            "profit_loss_percent": (
                profit_loss_percent
            ),
            "symbols": reports,
        }

    def _invested_for_symbol(
        self,
        symbol: str,
    ) -> float:
        performance = (
            IPOPaperPerformanceService(
                self._orders_for_symbol(symbol)
            )
        )

        return performance.total_invested()

    def reset(
        self,
    ) -> None:
        """
        Reset performance by resetting the
        underlying paper execution services.
        """

        for symbol in self.monitor.symbols():
            controller = self.monitor._ipos[
                symbol
            ]["controller"]

            reset = getattr(
                controller,
                "reset",
                None,
            )

            if callable(reset):
                reset()