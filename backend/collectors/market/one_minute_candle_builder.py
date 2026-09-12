from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class _CandleState:
    symbol: str
    minute: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int | None = None


class OneMinuteCandleBuilder:
    """
    Convert live market ticks into completed 1-minute candles.

    Input:
        {
            "symbol": "ARCIIL-SM",
            "timestamp": datetime(...),
            "price": 100.50,
            "volume": 1200,
        }

    Output:
        A completed candle only when the tick belongs
        to a new minute.

    The currently forming candle is never emitted as
    a completed candle until the minute changes.
    """

    def __init__(self):
        self._states: dict[str, _CandleState] = {}

    @staticmethod
    def _minute_bucket(timestamp: datetime) -> datetime:
        return timestamp.replace(
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _validate_tick(
        tick: dict[str, Any],
    ) -> None:
        if not isinstance(tick, dict):
            raise ValueError("tick must be a dictionary.")

        symbol = tick.get("symbol")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("tick symbol is required.")

        timestamp = tick.get("timestamp")

        if not isinstance(timestamp, datetime):
            raise ValueError(
                "tick timestamp must be a datetime."
            )

        try:
            price = float(tick["price"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "tick price must be numeric."
            ) from None

        if price <= 0:
            raise ValueError(
                "tick price must be greater than zero."
            )

        if tick.get("volume") is not None:
            try:
                volume = int(tick["volume"])
            except (TypeError, ValueError):
                raise ValueError(
                    "tick volume must be numeric."
                ) from None

            if volume < 0:
                raise ValueError(
                    "tick volume cannot be negative."
                )

    def update(
        self,
        tick: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Add one tick.

        Returns:
            None
                if the candle is still forming.

            dict
                when the previous minute's candle is completed.
        """

        self._validate_tick(tick)

        symbol = tick["symbol"].strip().upper()
        timestamp = tick["timestamp"]
        price = float(tick["price"])

        volume = tick.get("volume")

        if volume is not None:
            volume = int(volume)

        minute = self._minute_bucket(timestamp)

        current = self._states.get(symbol)

        # First tick for this symbol.
        if current is None:
            self._states[symbol] = _CandleState(
                symbol=symbol,
                minute=minute,
                open_price=price,
                high_price=price,
                low_price=price,
                close_price=price,
                volume=volume,
            )

            return None

        # Same minute: update current candle.
        if minute == current.minute:
            current.high_price = max(
                current.high_price,
                price,
            )

            current.low_price = min(
                current.low_price,
                price,
            )

            current.close_price = price

            if volume is not None:
                current.volume = volume

            return None

        # New minute: finalize previous candle.
        completed = {
            "symbol": current.symbol,
            "timestamp": current.minute,
            "open": current.open_price,
            "high": current.high_price,
            "low": current.low_price,
            "close": current.close_price,
            "volume": current.volume,
            "interval": "1m",
            "source": "angel_one_websocket",
        }

        # Start the new candle.
        self._states[symbol] = _CandleState(
            symbol=symbol,
            minute=minute,
            open_price=price,
            high_price=price,
            low_price=price,
            close_price=price,
            volume=volume,
        )

        return completed

    def flush(
        self,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Flush currently forming candles.

        Normally used when the trading session ends or
        when the builder is being reset.
        """

        if symbol is not None:
            normalized = symbol.strip().upper()

            state = self._states.pop(
                normalized,
                None,
            )

            if state is None:
                return []

            return [
                self._to_candle(state)
            ]

        candles = [
            self._to_candle(state)
            for state in self._states.values()
        ]

        self._states.clear()

        return candles

    def reset(
        self,
        symbol: str | None = None,
    ) -> None:
        """Reset candle-building state."""

        if symbol is None:
            self._states.clear()
            return

        self._states.pop(
            symbol.strip().upper(),
            None,
        )

    @staticmethod
    def _to_candle(
        state: _CandleState,
    ) -> dict[str, Any]:
        return {
            "symbol": state.symbol,
            "timestamp": state.minute,
            "open": state.open_price,
            "high": state.high_price,
            "low": state.low_price,
            "close": state.close_price,
            "volume": state.volume,
            "interval": "1m",
            "source": "angel_one_websocket",
        }