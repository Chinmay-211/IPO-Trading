from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LiveCandle:
    """Completed one-minute OHLCV candle."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval: str = "1m"
    source: str = "angel_one"


class OneMinuteCandleBuilder:
    """
    Builds one-minute OHLCV candles from live market ticks.

    One active candle is maintained independently for each symbol.

    A candle is completed when a tick arrives belonging to a
    different minute.
    """

    def __init__(self):
        self._active: dict[str, LiveCandle] = {}

    @staticmethod
    def _minute(timestamp: datetime) -> datetime:
        """Normalize a timestamp to the beginning of its minute."""

        return timestamp.replace(
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _validate_tick(tick: dict) -> None:
        if not isinstance(tick, dict):
            raise ValueError("tick must be a dictionary.")

        required = (
            "symbol",
            "timestamp",
            "price",
            "volume",
        )

        for field in required:
            if field not in tick:
                raise ValueError(
                    f"tick is missing required field: {field}"
                )

        if not isinstance(tick["symbol"], str):
            raise ValueError("tick symbol must be a string.")

        if not tick["symbol"].strip():
            raise ValueError("tick symbol is required.")

        if not isinstance(tick["timestamp"], datetime):
            raise ValueError(
                "tick timestamp must be a datetime."
            )

        try:
            price = float(tick["price"])
        except (TypeError, ValueError):
            raise ValueError(
                "tick price must be numeric."
            ) from None

        if price <= 0:
            raise ValueError(
                "tick price must be greater than zero."
            )

        try:
            volume = int(tick["volume"])
        except (TypeError, ValueError):
            raise ValueError(
                "tick volume must be an integer."
            ) from None

        if volume < 0:
            raise ValueError(
                "tick volume cannot be negative."
            )

    def update(
        self,
        tick: dict,
    ) -> LiveCandle | None:
        """
        Process one live tick.

        Returns:
            None:
                The tick belongs to the currently active candle.

            LiveCandle:
                The previous candle when this tick starts a new minute.
        """

        self._validate_tick(tick)

        symbol = tick["symbol"].strip().upper()
        timestamp = tick["timestamp"]
        price = float(tick["price"])
        volume = int(tick["volume"])

        minute = self._minute(timestamp)

        active = self._active.get(symbol)

        # First tick for this symbol.
        if active is None:
            self._active[symbol] = LiveCandle(
                symbol=symbol,
                timestamp=minute,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
            )

            return None

        # Same minute: update current candle.
        if minute == active.timestamp:
            active.high = max(active.high, price)
            active.low = min(active.low, price)
            active.close = price
            active.volume += volume

            return None

        # Older tick: ignore it rather than corrupting
        # the already progressing candle stream.
        if minute < active.timestamp:
            return None

        # New minute: close previous candle.
        completed = active

        self._active[symbol] = LiveCandle(
            symbol=symbol,
            timestamp=minute,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
        )

        return completed

    def flush(
        self,
        symbol: str,
    ) -> LiveCandle | None:
        """
        Complete and remove the currently active candle.

        Useful at the end of a trading session.
        """

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol is required.")

        return self._active.pop(
            normalized_symbol,
            None,
        )

    def reset(self) -> None:
        """Remove all active candles."""

        self._active.clear()

    def get_active(
        self,
        symbol: str,
    ) -> LiveCandle | None:
        """Return the currently active candle without removing it."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol is required.")

        return self._active.get(normalized_symbol)