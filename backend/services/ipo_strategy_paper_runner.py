from typing import Any

from backend.services.ipo_paper_trading_batch import (
    IPOPaperTradingBatch,
)


class IPOStrategyPaperRunner:
    """
    Connects IPO screening decisions with paper execution.

    Only IPOs that pass the screening strategy are sent
    to the paper-trading layer.
    """

    def __init__(
        self,
        paper_trading_batch: IPOPaperTradingBatch,
    ):
        if paper_trading_batch is None:
            raise ValueError(
                "paper_trading_batch is required."
            )

        self.paper_trading_batch = paper_trading_batch

    @staticmethod
    def _passed_screening(
        screening: dict[str, Any],
    ) -> bool:
        if not isinstance(screening, dict):
            return False

        status = screening.get("status")

        if status in {
            "PASS",
            "PASSED",
            "APPROVED",
            "TRADE",
        }:
            return True

        if screening.get("passed") is True:
            return True

        if screening.get("eligible") is True:
            return True

        return False

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
        Execute one screened IPO through paper trading.
        """

        if not isinstance(ipo, dict):
            raise ValueError("ipo must be a dictionary.")

        if not isinstance(screening, dict):
            raise ValueError(
                "screening must be a dictionary."
            )

        if not self._passed_screening(screening):
            return {
                "status": "NO_TRADE",
                "symbol": ipo.get("symbol"),
                "reason": (
                    "IPO did not pass the screening strategy."
                ),
                "screening": screening,
            }

        result = self.paper_trading_batch.run_one(
            ipo=ipo,
            candles=candles,
            quantity=quantity,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
        )

        result["screening"] = screening

        return result

    def run_batch(
        self,
        opportunities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Process multiple screened IPO opportunities.

        Each opportunity must contain:

            ipo
            screening
            candles
            quantity
            entry_price
            target_price
            stop_loss_price
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