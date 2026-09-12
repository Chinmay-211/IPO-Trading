from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class OneMinuteCandleBuilder:
    """
    Converts live ticks into completed 1-minute candles.

    A candle is emitted when a tick belonging to a new minute
    arrives, meaning the previous minute is complete.
    """

    def __init__(self):
        self._current: dict[str, Candle] = {}

    @staticmethod
    def _minute(timestamp: datetime) -> datetime:
        return timestamp.replace(
            second=0,
            microsecond=0,
        )

    def update(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        volume: int = 0,
    ) -> Candle | None:

        symbol = symbol.strip().upper()

        if not symbol:
            raise ValueError("symbol is required.")

        if price <= 0:
            raise ValueError("price must be positive.")

        minute = self._minute(timestamp)

        current = self._current.get(symbol)

        # First tick for this symbol.
        if current is None:
            self._current[symbol] = Candle(
                symbol=symbol,
                timestamp=minute,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
            )
            return None

        # Same minute: update existing candle.
        if minute == current.timestamp:
            current.high = max(current.high, price)
            current.low = min(current.low, price)
            current.close = price
            current.volume += volume
            return None

        # New minute: previous candle is now complete.
        completed = current

        self._current[symbol] = Candle(
            symbol=symbol,
            timestamp=minute,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
        )

        return completed

    def flush(self, symbol: str) -> Candle | None:
        """
        Return the currently accumulated candle.

        Intended for controlled shutdown/end-of-session handling.
        """

        symbol = symbol.strip().upper()

        return self._current.pop(symbol, None)

    def reset(self) -> None:
        self._current.clear()