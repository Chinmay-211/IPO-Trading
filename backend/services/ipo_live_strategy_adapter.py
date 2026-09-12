from __future__ import annotations

from typing import Any, Callable

from backend.strategy.ipo_listing_day_strategy import (
    IPOListingDayStrategy,
    IPOListingTradeResult,
)


class IPOLiveStrategyAdapter:
    """
    Connects completed live candles to IPOListingDayStrategy.

    The existing strategy remains unchanged.

    Flow:

        completed candle
            ↓
        candle buffer
            ↓
        IPOListingDayStrategy.run(...)
            ↓
        IPOListingTradeResult

    This class does NOT execute orders.
    """

    def __init__(
        self,
        strategy: IPOListingDayStrategy | None = None,
        strategy_result: str = "PASS",
        on_result: Callable[
            [IPOListingTradeResult], Any
        ] | None = None,
    ):
        if strategy is None:
            strategy = IPOListingDayStrategy()

        if not isinstance(strategy_result, str):
            raise ValueError(
                "strategy_result must be a string."
            )

        self.strategy = strategy
        self.strategy_result = strategy_result
        self.on_result = on_result

        self.candles: list[dict[str, Any]] = []
        self.last_result: IPOListingTradeResult | None = None

    def add_candle(
        self,
        candle: dict[str, Any],
    ) -> IPOListingTradeResult:
        """
        Add one completed candle and evaluate the
        accumulated listing-day candle sequence.
        """

        if not isinstance(candle, dict):
            raise ValueError(
                "candle must be a dictionary."
            )

        required_fields = (
            "timestamp",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
        )

        missing = [
            field
            for field in required_fields
            if field not in candle
        ]

        if missing:
            raise ValueError(
                "Candle is missing required fields: "
                + ", ".join(missing)
            )

        self.candles.append(dict(candle))

        result = self.strategy.run(
            candles=list(self.candles),
            strategy_result=self.strategy_result,
        )

        if not isinstance(result, IPOListingTradeResult):
            raise TypeError(
                "IPOListingDayStrategy.run() must return "
                "IPOListingTradeResult."
            )

        self.last_result = result

        if self.on_result is not None:
            self.on_result(result)

        return result

    def add_candles(
        self,
        candles: list[dict[str, Any]],
    ) -> IPOListingTradeResult:
        """
        Add multiple completed candles in chronological order.
        """

        if not isinstance(candles, list):
            raise ValueError(
                "candles must be a list."
            )

        result = None

        for candle in candles:
            result = self.add_candle(candle)

        if result is None:
            result = self.strategy.run(
                candles=[],
                strategy_result=self.strategy_result,
            )

            self.last_result = result

        return result

    def get_candles(self) -> list[dict[str, Any]]:
        """Return a copy of the accumulated candles."""

        return list(self.candles)

    def get_last_result(
        self,
    ) -> IPOListingTradeResult | None:
        """Return the latest strategy result."""

        return self.last_result

    def reset(self) -> None:
        """Reset the live listing-day strategy state."""

        self.candles.clear()
        self.last_result = None