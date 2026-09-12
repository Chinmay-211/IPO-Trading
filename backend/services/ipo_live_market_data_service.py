from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


class IPOLiveMarketDataService:
    """
    Receives live market ticks and builds 1-minute candles.

    This service does NOT make trading decisions.

    Flow:

        Angel One WebSocket
                ↓
             tick
                ↓
        IPOLiveMarketDataService
                ↓
          completed candle
                ↓
        candle callback
                ↓
        paper-trading controller
    """

    def __init__(
        self,
        on_candle: Callable[[dict[str, Any]], Any] | None = None,
    ):
        self.on_candle = on_candle

        self._current_minute: datetime | None = None
        self._current_candle: dict[str, Any] | None = None

    @staticmethod
    def _normalize_timestamp(
        timestamp: datetime,
    ) -> datetime:
        """
        Normalize timestamp to minute precision.
        """

        return timestamp.replace(
            second=0,
            microsecond=0,
        )

    def process_tick(
        self,
        symbol: str,
        price: float,
        volume: int | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, Any] | None:
        """
        Process one live tick.

        A new minute finalizes the previous candle.

        Returns:
            completed candle, or None if the current
            candle is still being built.
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "symbol is required."
            )

        price = float(price)

        if price <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        if timestamp is None:
            timestamp = datetime.now()

        minute = self._normalize_timestamp(
            timestamp
        )

        symbol = symbol.strip().upper()

        # First tick.
        if self._current_candle is None:
            self._start_candle(
                symbol=symbol,
                price=price,
                volume=volume,
                minute=minute,
            )

            return None

        # Same minute: update candle.
        if minute == self._current_minute:
            self._update_candle(
                price=price,
                volume=volume,
            )

            return None

        # New minute: finalize previous candle.
        completed = self._finalize_candle()

        # Start new candle.
        self._start_candle(
            symbol=symbol,
            price=price,
            volume=volume,
            minute=minute,
        )

        return completed

    def _start_candle(
        self,
        symbol: str,
        price: float,
        volume: int | None,
        minute: datetime,
    ) -> None:
        self._current_minute = minute

        self._current_candle = {
            "symbol": symbol,
            "timestamp": minute,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": (
                int(volume)
                if volume is not None
                else None
            ),
            "source": "angel_one_websocket",
            "interval": "1m",
        }

    def _update_candle(
        self,
        price: float,
        volume: int | None,
    ) -> None:
        if self._current_candle is None:
            return

        self._current_candle["high"] = max(
            self._current_candle["high"],
            price,
        )

        self._current_candle["low"] = min(
            self._current_candle["low"],
            price,
        )

        self._current_candle["close"] = price

        if volume is not None:
            current_volume = (
                self._current_candle["volume"]
            )

            if current_volume is None:
                self._current_candle["volume"] = int(
                    volume
                )
            else:
                self._current_candle["volume"] = (
                    int(current_volume) + int(volume)
                )

    def _finalize_candle(
        self,
    ) -> dict[str, Any] | None:
        if self._current_candle is None:
            return None

        candle = dict(
            self._current_candle
        )

        if self.on_candle is not None:
            self.on_candle(candle)

        return candle

    def flush(self) -> dict[str, Any] | None:
        """
        Finalize the currently open candle.

        Useful when the market session ends.
        """

        candle = self._finalize_candle()

        self._current_minute = None
        self._current_candle = None

        return candle

    def reset(self) -> None:
        """
        Clear the current candle.
        """

        self._current_minute = None
        self._current_candle = None