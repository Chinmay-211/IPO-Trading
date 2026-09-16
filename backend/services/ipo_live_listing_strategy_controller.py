from __future__ import annotations

from datetime import datetime, time
from typing import Any, Callable


class IPOLiveListingStrategyController:
    """
    Stateful live implementation of the IPO listing-day rules.

    This controller is intentionally separate from
    IPOListingDayStrategy because that class evaluates a
    completed candle series/backtest.

    Live flow:

        5 observation candles
              ↓
        wait for 2% dip
              ↓
        wait for recovery above opening price
              ↓
        require 1.5x volume confirmation
              ↓
        BUY at next candle OPEN
              ↓
        monitor stop / target
              ↓
        force exit at 15:15

    This controller only produces strategy decisions.
    It does not place orders directly.
    """

    OBSERVATION_CANDLES = 5
    DIP_PERCENT = 2.0
    VOLUME_MULTIPLIER = 1.5
    MAX_STOP_PERCENT = 3.0
    REWARD_RISK = 2.0

    LAST_ENTRY_TIME = time(14, 30)
    FORCE_EXIT_TIME = time(15, 15)

    def __init__(
        self,
        symbol: str,
        quantity: int,
        screening_passed: bool = True,
        on_decision: Callable[
            [dict[str, Any]], Any
        ] | None = None,
    ):
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if int(quantity) <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        self.symbol = symbol.strip().upper()
        self.quantity = int(quantity)
        self.screening_passed = bool(
            screening_passed
        )
        self.on_decision = on_decision

        self.candles: list[dict[str, Any]] = []

        self.opening_price: float | None = None
        self.dip_low: float | None = None

        self.confirmed = False
        self.entry_pending = False
        self.position_open = False
        self.closed = False

        self.entry_price: float | None = None
        self.entry_time: datetime | None = None

        self.stop_loss_price: float | None = None
        self.target_price: float | None = None

        self.last_decision: dict[str, Any] | None = None

    def process_candle(
        self,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Process one completed 1-minute candle.

        Returns a strategy decision when an actionable
        event occurs; otherwise None.
        """

        normalized = self._normalize_candle(candle)
        self.candles.append(normalized)

        timestamp = normalized["timestamp"]
        open_price = normalized["open_price"]
        high_price = normalized["high_price"]
        low_price = normalized["low_price"]
        close_price = normalized["close_price"]
        volume = normalized["volume"]

        if self.closed:
            return None

        if not self.screening_passed:
            return self._emit(
                {
                    "action": "NO_TRADE",
                    "symbol": self.symbol,
                    "quantity": self.quantity,
                    "price": close_price,
                    "timestamp": timestamp,
                    "reason": (
                        "IPO did not pass the 13-rule "
                        "screening strategy."
                    ),
                }
            )

        if self.opening_price is None:
            self.opening_price = open_price

        if self.position_open:
            return self._process_open_position(
                timestamp=timestamp,
                high_price=high_price,
                low_price=low_price,
                open_price=open_price,
                close_price=close_price,
            )

        if self.entry_pending:
            return self._enter_at_next_open(
                timestamp=timestamp,
                open_price=open_price,
            )

        if not self.confirmed:
            self._check_dip(
                low_price
            )

        if len(self.candles) < self.OBSERVATION_CANDLES:
            return None

        if not self.confirmed:
            if self.dip_low is None:
                return None

            if timestamp.time() > self.LAST_ENTRY_TIME:
                return self._no_trade(
                    timestamp,
                    "No confirmed entry before 14:30.",
                )

            if self._confirmation_exists(
                close_price=close_price,
                volume=volume,
            ):
                self.confirmed = True
                self.entry_pending = True

            return None

        return None

    def _check_dip(
        self,
        low_price: float | None,
    ) -> None:
        if low_price is None:
            return

        if self.opening_price is None:
            return

        required_dip = (
            self.opening_price
            * (1 - self.DIP_PERCENT / 100)
        )

        if low_price <= required_dip:
            if self.dip_low is None:
                self.dip_low = low_price
            else:
                self.dip_low = min(
                    self.dip_low,
                    low_price,
                )

    def _confirmation_exists(
        self,
        close_price: float | None,
        volume: int | None,
    ) -> bool:
        if (
            close_price is None
            or self.opening_price is None
            or close_price <= self.opening_price
        ):
            return False

        if volume is None:
            return False

        previous = self.candles[-6:-1]

        if len(previous) < 5:
            return False

        volumes = [
            candle["volume"]
            for candle in previous
            if candle["volume"] is not None
        ]

        if len(volumes) < 5:
            return False

        average_volume = (
            sum(volumes) / len(volumes)
        )

        return volume >= (
            average_volume
            * self.VOLUME_MULTIPLIER
        )

    def _enter_at_next_open(
        self,
        timestamp: datetime,
        open_price: float,
    ) -> dict[str, Any] | None:
        self.entry_pending = False

        if timestamp.time() > self.LAST_ENTRY_TIME:
            return self._no_trade(
                timestamp,
                "BUY signal occurs after the allowed entry time.",
            )

        if self.dip_low is None:
            return None

        risk_floor = (
            open_price
            * (1 - self.MAX_STOP_PERCENT / 100)
        )

        self.stop_loss_price = max(
            self.dip_low,
            risk_floor,
        )

        risk = (
            open_price
            - self.stop_loss_price
        )

        if risk <= 0:
            self.closed = True

            return self._emit(
                {
                    "action": "NO_TRADE",
                    "symbol": self.symbol,
                    "quantity": self.quantity,
                    "price": open_price,
                    "timestamp": timestamp,
                    "reason": (
                        "Calculated stop-loss is not "
                        "below entry."
                    ),
                }
            )

        self.entry_price = open_price
        self.entry_time = timestamp

        self.target_price = (
            open_price
            + risk * self.REWARD_RISK
        )

        self.position_open = True

        return self._emit(
            {
                "action": "BUY",
                "symbol": self.symbol,
                "quantity": self.quantity,
                "price": open_price,
                "timestamp": timestamp,
                "stop_loss_price": (
                    self.stop_loss_price
                ),
                "target_price": self.target_price,
                "reason": (
                    "Listing-day dip and volume "
                    "confirmation completed."
                ),
            }
        )

    def _process_open_position(
        self,
        timestamp: datetime,
        high_price: float | None,
        low_price: float | None,
        open_price: float,
        close_price: float | None,
    ) -> dict[str, Any] | None:
        if (
            timestamp.time()
            >= self.FORCE_EXIT_TIME
        ):
            exit_price = (
                open_price
                if open_price is not None
                else close_price
            )

            return self._close_position(
                timestamp,
                exit_price,
                "TIME_EXIT",
                "Forced exit at 15:15.",
            )

        stop_hit = (
            low_price is not None
            and self.stop_loss_price is not None
            and low_price <= self.stop_loss_price
        )

        target_hit = (
            high_price is not None
            and self.target_price is not None
            and high_price >= self.target_price
        )

        if stop_hit:
            return self._close_position(
                timestamp,
                self.stop_loss_price,
                "STOP_LOSS",
                "Stop-loss was reached.",
            )

        if target_hit:
            return self._close_position(
                timestamp,
                self.target_price,
                "TARGET",
                "2R target was reached.",
            )

        return None

    def _close_position(
        self,
        timestamp: datetime,
        exit_price: float | None,
        outcome: str,
        reason: str,
    ) -> dict[str, Any] | None:
        if exit_price is None:
            return None

        self.position_open = False
        self.closed = True

        return self._emit(
            {
                "action": "SELL",
                "symbol": self.symbol,
                "quantity": self.quantity,
                "price": float(exit_price),
                "timestamp": timestamp,
                "outcome": outcome,
                "entry_price": self.entry_price,
                "stop_loss_price": self.stop_loss_price,
                "target_price": self.target_price,
                "reason": reason,
            }
        )

    def _no_trade(
        self,
        timestamp: datetime,
        reason: str,
    ) -> dict[str, Any]:
        self.closed = True

        return self._emit(
            {
                "action": "NO_TRADE",
                "symbol": self.symbol,
                "quantity": self.quantity,
                "price": None,
                "timestamp": timestamp,
                "reason": reason,
            }
        )

    def _emit(
        self,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_decision = decision

        if self.on_decision is not None:
            self.on_decision(decision)

        return decision

    @staticmethod
    def _normalize_candle(
        candle: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(candle, dict):
            raise ValueError(
                "candle must be a dictionary."
            )

        timestamp = candle.get("timestamp")

        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(
                timestamp
            )

        if not isinstance(timestamp, datetime):
            raise ValueError(
                "candle timestamp is required."
            )

        def price(
            modern_key: str,
            legacy_key: str,
        ):
            value = candle.get(modern_key)

            if value is None:
                value = candle.get(legacy_key)

            if value is None:
                raise ValueError(
                    f"{modern_key} is required."
                )

            return float(value)

        volume = candle.get("volume")

        if volume is not None:
            volume = int(volume)

        return {
            "symbol": str(
                candle.get(
                    "symbol",
                    "",
                )
            ).strip().upper(),
            "timestamp": timestamp,
            "open_price": price(
                "open_price",
                "open",
            ),
            "high_price": price(
                "high_price",
                "high",
            ),
            "low_price": price(
                "low_price",
                "low",
            ),
            "close_price": price(
                "close_price",
                "close",
            ),
            "volume": volume,
        }

    def get_state(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "candles": len(self.candles),
            "opening_price": self.opening_price,
            "dip_low": self.dip_low,
            "confirmed": self.confirmed,
            "entry_pending": self.entry_pending,
            "position_open": self.position_open,
            "closed": self.closed,
            "entry_price": self.entry_price,
            "stop_loss_price": self.stop_loss_price,
            "target_price": self.target_price,
            "last_decision": self.last_decision,
        }

    def reset(self) -> None:
        self.candles.clear()

        self.opening_price = None
        self.dip_low = None

        self.confirmed = False
        self.entry_pending = False
        self.position_open = False
        self.closed = False

        self.entry_price = None
        self.entry_time = None
        self.stop_loss_price = None
        self.target_price = None

        self.last_decision = None