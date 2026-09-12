from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class CandleState:
    """
    Mutable state for the currently forming candle.
    """

    symbol: str
    timestamp: datetime

    open_price: float
    high_price: float
    low_price: float
    close_price: float

    volume: int = 0


class OneMinuteCandleBuilder:
    """
    Convert live market ticks into 1-minute OHLCV candles.

    A new minute automatically closes the previous candle.

    Example:

        tick 09:15:01 -> candle 09:15
        tick 09:15:30 -> updates 09:15
        tick 09:15:59 -> updates 09:15
        tick 09:16:01 -> closes 09:15
                         starts 09:16
    """

    def __init__(self):
        self._current: CandleState | None = None

    @staticmethod
    def _minute_start(timestamp: datetime) -> datetime:
        """
        Normalize a timestamp to the beginning of its minute.
        """

        return timestamp.replace(
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _extract_price(tick: dict[str, Any]) -> float:
        """
        Extract LTP from an Angel One tick.

        Supported fields:

            last_traded_price
            ltp
            price
        """

        for field in (
            "last_traded_price",
            "ltp",
            "price",
        ):
            value = tick.get(field)

            if value is not None:
                return float(value)

        raise ValueError(
            "Tick does not contain a valid price."
        )

    @staticmethod
    def _extract_timestamp(
        tick: dict[str, Any],
    ) -> datetime:
        """
        Extract tick timestamp.

        Supports:

            datetime
            ISO timestamp string

        If no timestamp is supplied, the caller should
        provide one before passing the tick here.
        """

        value = tick.get("timestamp")

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            return datetime.fromisoformat(value)

        raise ValueError(
            "Tick does not contain a valid timestamp."
        )

    @staticmethod
    def _extract_volume(
        tick: dict[str, Any],
    ) -> int:
        """
        Extract volume when available.

        Missing volume is treated as zero.
        """

        value = tick.get("volume")

        if value is None:
            return 0

        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_candle(
        state: CandleState,
    ) -> dict[str, Any]:
        """
        Convert internal candle state into the project's
        normalized candle representation.
        """

        return {
            "symbol": state.symbol,
            "timestamp": state.timestamp,
            "open": state.open_price,
            "high": state.high_price,
            "low": state.low_price,
            "close": state.close_price,
            "volume": state.volume,
            "source": "angel_one_websocket",
            "interval": "1m",
        }

    def update(
        self,
        tick: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Add one tick.

        Returns:

            None
                if the current 1-minute candle is still forming.

            dict
                when the previous candle has just completed.
        """

        if not isinstance(tick, dict):
            raise ValueError(
                "tick must be a dictionary."
            )

        symbol = tick.get("symbol")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "tick symbol is required."
            )

        symbol = symbol.strip().upper()

        timestamp = self._extract_timestamp(tick)
        price = self._extract_price(tick)
        volume = self._extract_volume(tick)

        minute = self._minute_start(timestamp)

        # First tick.
        if self._current is None:
            self._current = CandleState(
                symbol=symbol,
                timestamp=minute,
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=volume,
            )

            return None

        # Reject an out-of-order tick from an older minute.
        if minute < self._current.timestamp:
            return None

        # Same minute: update current candle.
        if minute == self._current.timestamp:

            self._current.high_price = max(
                self._current.high_price,
                price,
            )

            self._current.low_price = min(
                self._current.low_price,
                price,
            )

            self._current.close_price = price

            self._current.volume += volume

            return None

        # New minute: previous candle is complete.
        completed = self._to_candle(
            self._current
        )

        # Start the new candle.
        self._current = CandleState(
            symbol=symbol,
            timestamp=minute,
            open_price=price,
            high_price=price,
            low_price=price,
            close_price=price,
            volume=volume,
        )

        return completed

    def flush(self) -> dict[str, Any] | None:
        """
        Close and return the currently forming candle.

        Useful when the market session ends.
        """

        if self._current is None:
            return None

        completed = self._to_candle(
            self._current
        )

        self._current = None

        return completed

    def reset(self) -> None:
        """
        Clear the current candle state.
        """

        self._current = None

    @property
    def current_candle(self) -> dict[str, Any] | None:
        """
        Return the currently forming candle without closing it.
        """

        if self._current is None:
            return None

        return self._to_candle(
            self._current
        )