from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class LiveCandle:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    source: str = "angel_one_websocket"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "source": self.source,
        }


class AngelOneLiveCandleBuilder:
    """
    Converts Angel One live ticks into one-minute OHLC candles.

    This class does not:
        - make trading decisions
        - place orders
        - modify screening rules
        - access the paper broker

    It only converts ticks into candles.
    """

    def __init__(self):
        self._candles: dict[str, LiveCandle] = {}

    @staticmethod
    def _minute_timestamp(timestamp: datetime) -> datetime:
        return timestamp.replace(
            second=0,
            microsecond=0,
        )

    def update(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        volume: int | None = None,
    ) -> LiveCandle:

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a datetime.")

        price = float(price)

        if price <= 0:
            raise ValueError("price must be greater than zero.")

        normalized_symbol = symbol.strip().upper()
        candle_timestamp = self._minute_timestamp(timestamp)

        key = (
            normalized_symbol,
            candle_timestamp.isoformat(),
        )

        existing = self._candles.get(key)

        if existing is None:
            candle = LiveCandle(
                symbol=normalized_symbol,
                timestamp=candle_timestamp,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
            )

            self._candles[key] = candle

            return candle

        existing.high = max(existing.high, price)
        existing.low = min(existing.low, price)
        existing.close = price

        if volume is not None:
            existing.volume = volume

        return existing

    def get(
        self,
        symbol: str,
        timestamp: datetime,
    ) -> LiveCandle | None:

        normalized_symbol = symbol.strip().upper()
        candle_timestamp = self._minute_timestamp(timestamp)

        key = (
            normalized_symbol,
            candle_timestamp.isoformat(),
        )

        return self._candles.get(key)

    def get_all(
        self,
        symbol: str | None = None,
    ) -> list[LiveCandle]:

        candles = list(self._candles.values())

        if symbol is not None:
            normalized_symbol = symbol.strip().upper()
            candles = [
                candle
                for candle in candles
                if candle.symbol == normalized_symbol
            ]

        return sorted(
            candles,
            key=lambda candle: candle.timestamp,
        )

    def flush(
        self,
        symbol: str,
        timestamp: datetime,
    ) -> LiveCandle | None:

        candle = self.get(
            symbol=symbol,
            timestamp=timestamp,
        )

        if candle is None:
            return None

        key = (
            candle.symbol,
            candle.timestamp.isoformat(),
        )

        self._candles.pop(key, None)

        return candle

    def reset(self) -> None:
        self._candles.clear()