from typing import Any

from backend.services.ipo_strategy_paper_runner import (
    IPOStrategyPaperRunner,
)


class IPOScreeningPaperPipeline:
    """
    End-to-end bridge from IPO screening to paper trading.

    Flow:

        screening result
            ↓
        PASS / FAIL
            ↓
        paper trading for PASS only
    """

    def __init__(
        self,
        paper_runner: IPOStrategyPaperRunner,
    ):
        if paper_runner is None:
            raise ValueError(
                "paper_runner is required."
            )

        self.paper_runner = paper_runner

    def run_one(
        self,
        ipo: dict[str, Any],
        screening: dict[str, Any],
        candles: list[dict[str, Any]],
        quantity: int,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
    ) -> dict[str, Any]:
        """
        Run one IPO through screening and paper execution.
        """

        if not isinstance(ipo, dict):
            raise ValueError(
                "ipo must be a dictionary."
            )

        if not isinstance(screening, dict):
            raise ValueError(
                "screening must be a dictionary."
            )

        result = self.paper_runner.run_one(
            ipo=ipo,
            screening=screening,
            candles=candles,
            quantity=quantity,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
        )

        return result

    def run_batch(
        self,
        opportunities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Run multiple IPOs through the paper pipeline.
        """

        if not isinstance(opportunities, list):
            raise ValueError(
                "opportunities must be a list."
            )

        results = []

        for opportunity in opportunities:
            if not isinstance(opportunity, dict):
                raise ValueError(
                    "Each opportunity must be a dictionary."
                )

            result = self.run_one(
                ipo=opportunity["ipo"],
                screening=opportunity["screening"],
                candles=opportunity["candles"],
                quantity=opportunity["quantity"],
                entry_price=opportunity["entry_price"],
                target_price=opportunity["target_price"],
                stop_loss_price=opportunity["stop_loss_price"],
            )

            results.append(result)

        return results

    @staticmethod
    def summarize(
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Produce a compact summary of paper-trading results.
        """

        total = len(results)

        trades = [
            result
            for result in results
            if result.get("status") == "CLOSED"
        ]

        target_count = sum(
            result.get("exit_reason") == "TARGET"
            for result in trades
        )

        stop_loss_count = sum(
            result.get("exit_reason") == "STOP_LOSS"
            for result in trades
        )

        no_trade_count = sum(
            result.get("status") == "NO_TRADE"
            for result in results
        )

        open_count = sum(
            result.get("status") == "OPEN"
            for result in results
        )

        total_pnl = sum(
            float(result.get("profit_loss") or 0)
            for result in results
        )

        return {
            "total": total,
            "closed": len(trades),
            "target": target_count,
            "stop_loss": stop_loss_count,
            "no_trade": no_trade_count,
            "open": open_count,
            "total_profit_loss": total_pnl,
        }