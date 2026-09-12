from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)


@dataclass
class LiveIPOState:
    """Runtime state for one IPO being monitored."""

    ipo_id: int | None
    symbol: str
    listing_date: str

    screening: dict[str, Any]

    candles: list[dict[str, Any]] = field(
        default_factory=list
    )

    status: str = "MONITORING"

    entry_price: float | None = None
    entry_timestamp: datetime | None = None

    quantity: int = 0

    stop_loss_price: float | None = None
    target_price: float | None = None

    exit_price: float | None = None
    exit_timestamp: datetime | None = None
    exit_reason: str | None = None

    dip_low: float | None = None
    dip_percent: float | None = None

    confirmation_time: datetime | None = None
    confirmation_price: float | None = None

    volume_confirmed: bool = False

    reason: str | None = None


class LiveIPOListingDayEngine:
    """
    Processes completed live IPO candles.

    This class does NOT connect to Angel One directly.

    Expected flow:

        Angel One WebSocket
              ↓
        Tick normalizer
              ↓
        OneMinuteCandleBuilder
              ↓
        LiveIPOListingDayEngine
              ↓
        Existing IPO strategy
              ↓
        LivePaperTradingService
              ↓
        PaperBroker
    """

    MARKET_CLOSE_TIME = time(15, 15)

    def __init__(
        self,
        paper_service: LivePaperTradingService,
    ):
        if paper_service is None:
            raise ValueError(
                "paper_service is required."
            )

        self.paper_service = paper_service

        self._states: dict[str, LiveIPOState] = {}

    def register_ipo(
        self,
        ipo: dict[str, Any],
        screening: dict[str, Any],
        quantity: int,
    ) -> LiveIPOState:
        """
        Register an IPO for live paper monitoring.

        Only screening-approved IPOs are registered.
        """

        if not isinstance(ipo, dict):
            raise ValueError(
                "ipo must be a dictionary."
            )

        if not isinstance(screening, dict):
            raise ValueError(
                "screening must be a dictionary."
            )

        symbol = str(
            ipo.get("symbol") or ""
        ).strip().upper()

        if not symbol:
            raise ValueError(
                "IPO symbol is required."
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        if not self._passed_screening(screening):
            raise ValueError(
                "IPO did not pass screening."
            )

        listing_date = str(
            ipo.get("listing_date") or ""
        )

        if not listing_date:
            raise ValueError(
                "IPO listing_date is required."
            )

        state = LiveIPOState(
            ipo_id=ipo.get("id"),
            symbol=symbol,
            listing_date=listing_date,
            screening=screening,
            quantity=quantity,
        )

        self._states[symbol] = state

        return state

    @staticmethod
    def _passed_screening(
        screening: dict[str, Any],
    ) -> bool:
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

    def process_candle(
        self,
        symbol: str,
        candle: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process one completed one-minute candle.

        The candle must contain:

            timestamp
            open
            high
            low
            close
            volume
        """

        normalized_symbol = (
            symbol.strip().upper()
        )

        state = self._states.get(
            normalized_symbol
        )

        if state is None:
            return {
                "status": "IGNORED",
                "symbol": normalized_symbol,
                "reason": "IPO is not registered.",
            }

        if state.status in {
            "CLOSED",
            "NO_TRADE",
        }:
            return self._result(state)

        normalized = self._normalize_candle(
            candle
        )

        if normalized is None:
            return {
                "status": "IGNORED",
                "symbol": normalized_symbol,
                "reason": "Invalid candle.",
            }

        timestamp = normalized["timestamp"]

        # Do not process candles after the strategy cutoff.
        if timestamp.time() >= self.MARKET_CLOSE_TIME:
            if state.status == "POSITION_OPEN":
                return self._force_exit(
                    state,
                    normalized,
                    reason="MARKET_CUTOFF",
                )

            state.status = "NO_TRADE"
            state.reason = (
                "No valid entry occurred before 15:15."
            )

            return self._result(state)

        state.candles.append(normalized)

        if state.status == "MONITORING":
            return self._process_entry_logic(
                state
            )

        if state.status == "POSITION_OPEN":
            return self._process_exit_logic(
                state,
                normalized,
            )

        return self._result(state)

    @staticmethod
    def _normalize_candle(
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:

        if not isinstance(candle, dict):
            return None

        try:
            timestamp = candle["timestamp"]

            if not isinstance(
                timestamp,
                datetime,
            ):
                return None

            return {
                "timestamp": timestamp,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": int(candle["volume"]),
            }

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

    def _process_entry_logic(
        self,
        state: LiveIPOState,
    ) -> dict[str, Any]:

        candles = state.candles

        # We need enough candles to establish the
        # initial listing range.
        if not candles:
            return self._result(state)

        opening_price = candles[0]["open"]

        # Detect the lowest price seen after listing.
        current_low = min(
            candle["low"]
            for candle in candles
        )

        state.dip_low = current_low

        if opening_price > 0:
            state.dip_percent = (
                (
                    opening_price - current_low
                )
                / opening_price
            ) * 100

        # Strategy requires a 2% dip.
        if (
            state.dip_percent is None
            or state.dip_percent < 2.0
        ):
            return self._result(state)

        # Recovery must move back above the
        # opening price.
        latest = candles[-1]

        if latest["close"] <= opening_price:
            return self._result(state)

        state.confirmation_time = (
            latest["timestamp"]
        )

        state.confirmation_price = (
            latest["close"]
        )

        # Need a previous candle for volume comparison.
        if len(candles) < 2:
            return self._result(state)

        previous = candles[-2]

        previous_volume = previous["volume"]

        if previous_volume <= 0:
            return self._result(state)

        if (
            latest["volume"]
            < previous_volume * 1.5
        ):
            return self._result(state)

        state.volume_confirmed = True

        # BUY on the candle AFTER confirmation.
        #
        # Therefore confirmation itself does not
        # execute the BUY.
        if len(candles) < 2:
            return self._result(state)

        if (
            state.confirmation_time
            == latest["timestamp"]
        ):
            return self._result(state)

        return self._enter(
            state,
            latest,
        )

    def _enter(
        self,
        state: LiveIPOState,
        candle: dict[str, Any],
    ) -> dict[str, Any]:

        if state.status != "MONITORING":
            return self._result(state)

        entry_price = float(
            candle["close"]
        )

        if entry_price <= 0:
            return self._result(state)

        # 2% stop below entry.
        stop_loss = (
            entry_price * 0.98
        )

        # 2R target.
        risk = (
            entry_price - stop_loss
        )

        target = (
            entry_price + (risk * 2)
        )

        execution = self.paper_service.enter(
            symbol=state.symbol,
            quantity=state.quantity,
            price=entry_price,
            timestamp=candle["timestamp"],
        )

        state.status = "POSITION_OPEN"
        state.entry_price = entry_price
        state.entry_timestamp = (
            candle["timestamp"]
        )
        state.stop_loss_price = stop_loss
        state.target_price = target

        return {
            "status": "BUY",
            "symbol": state.symbol,
            "quantity": state.quantity,
            "price": entry_price,
            "timestamp": candle["timestamp"],
            "order": execution,
            "stop_loss_price": stop_loss,
            "target_price": target,
        }

    def _process_exit_logic(
        self,
        state: LiveIPOState,
        candle: dict[str, Any],
    ) -> dict[str, Any]:

        if (
            state.stop_loss_price is None
            or state.target_price is None
        ):
            return self._result(state)

        # Conservative same-candle assumption:
        # STOP LOSS is checked first.
        if (
            candle["low"]
            <= state.stop_loss_price
        ):
            return self._exit(
                state,
                candle,
                state.stop_loss_price,
                "STOP_LOSS",
            )

        if (
            candle["high"]
            >= state.target_price
        ):
            return self._exit(
                state,
                candle,
                state.target_price,
                "TARGET",
            )

        return self._result(state)

    def _exit(
        self,
        state: LiveIPOState,
        candle: dict[str, Any],
        price: float,
        reason: str,
    ) -> dict[str, Any]:

        execution = self.paper_service.exit(
            symbol=state.symbol,
            quantity=state.quantity,
            price=float(price),
            timestamp=candle["timestamp"],
        )

        state.status = "CLOSED"
        state.exit_price = float(price)
        state.exit_timestamp = (
            candle["timestamp"]
        )
        state.exit_reason = reason

        pnl = (
            float(price)
            - float(state.entry_price)
        ) * state.quantity

        pnl_percent = (
            (
                float(price)
                - float(state.entry_price)
            )
            / float(state.entry_price)
        ) * 100

        return {
            "status": "SELL",
            "symbol": state.symbol,
            "quantity": state.quantity,
            "price": float(price),
            "timestamp": candle["timestamp"],
            "reason": reason,
            "order": execution,
            "profit_loss": pnl,
            "profit_loss_percent": pnl_percent,
        }

    def _force_exit(
        self,
        state: LiveIPOState,
        candle: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:

        if state.status != "POSITION_OPEN":
            state.status = "NO_TRADE"
            state.reason = (
                "Trading window ended without entry."
            )

            return self._result(state)

        return self._exit(
            state,
            candle,
            candle["close"],
            reason,
        )

    @staticmethod
    def _result(
        state: LiveIPOState,
    ) -> dict[str, Any]:

        return {
            "status": state.status,
            "symbol": state.symbol,
            "quantity": state.quantity,
            "entry_price": state.entry_price,
            "stop_loss_price": (
                state.stop_loss_price
            ),
            "target_price": state.target_price,
            "exit_price": state.exit_price,
            "exit_timestamp": (
                state.exit_timestamp
            ),
            "exit_reason": state.exit_reason,
            "dip_low": state.dip_low,
            "dip_percent": state.dip_percent,
            "confirmation_time": (
                state.confirmation_time
            ),
            "confirmation_price": (
                state.confirmation_price
            ),
            "volume_confirmed": (
                state.volume_confirmed
            ),
            "reason": state.reason,
        }

    def get_state(
        self,
        symbol: str,
    ) -> LiveIPOState | None:

        return self._states.get(
            symbol.strip().upper()
        )

    def get_all_states(
        self,
    ) -> list[LiveIPOState]:

        return list(
            self._states.values()
        )

    def reset(self) -> None:
        self._states.clear()