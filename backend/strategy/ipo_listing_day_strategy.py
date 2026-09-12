from dataclasses import dataclass
from datetime import datetime, time


@dataclass
class IPOListingTradeResult:
    """Result of a listing-day intraday strategy."""

    outcome: str

    entry_time: str | None
    entry_price: float | None

    stop_loss_price: float | None
    target_price: float | None

    exit_time: str | None
    exit_price: float | None

    profit_loss: float | None
    profit_loss_percent: float | None

    dip_low: float | None
    dip_percent: float | None

    confirmation_time: str | None
    confirmation_price: float | None

    reason: str


class IPOListingDayStrategy:
    """
    Listing-day IPO trading strategy.

    Rules:

    1. Observe the first 5 one-minute candles.
    2. Price must subsequently fall at least 2% below
       the listing-day opening price.
    3. Price must then recover and a 1-minute candle must
       close above the opening price.
    4. Confirmation-candle volume must be at least 1.5x
       the average volume of the preceding 5 candles.
    5. BUY at the next candle's OPEN.
    6. Stop-loss is the dip low, capped at 3% maximum
       risk below entry.
    7. Target is 2R.
    8. No new entry after 14:30.
    9. If neither stop nor target occurs, exit at 15:15.
    10. If stop and target occur in the same candle and
        tick/order data is unavailable, assume STOP first.
    """

    OBSERVATION_CANDLES = 5

    DIP_PERCENT = 2.0

    VOLUME_MULTIPLIER = 1.5

    MAX_STOP_PERCENT = 3.0

    REWARD_RISK = 2.0

    LAST_ENTRY_TIME = time(14, 30)

    FORCE_EXIT_TIME = time(15, 15)

    def run(
        self,
        candles: list[dict],
        strategy_result: str = "PASS",
    ) -> IPOListingTradeResult:

        if strategy_result != "PASS":
            return self._no_trade(
                "IPO did not pass the 13-rule screening strategy."
            )

        if not candles:
            return self._not_evaluable(
                "No listing-day candles are available."
            )

        normalized = self._normalize_candles(
            candles
        )

        if len(normalized) < self.OBSERVATION_CANDLES:
            return self._not_evaluable(
                "At least 5 one-minute candles are required."
            )

        opening_price = normalized[0]["open_price"]

        if opening_price is None or opening_price <= 0:
            return self._not_evaluable(
                "Invalid listing-day opening price."
            )

        observation = normalized[
            :self.OBSERVATION_CANDLES
        ]

        observation_low = min(
            candle["low_price"]
            for candle in observation
            if candle["low_price"] is not None
        )

        required_dip_price = (
            opening_price
            * (1 - self.DIP_PERCENT / 100)
        )

        dip_low = None
        dip_percent = None

        for index in range(
            self.OBSERVATION_CANDLES,
            len(normalized),
        ):

            candle = normalized[index]

            low_price = candle["low_price"]

            if (
                low_price is not None
                and low_price <= required_dip_price
            ):
                dip_low = low_price
                dip_percent = (
                    (opening_price - dip_low)
                    / opening_price
                    * 100
                )

                break

        if dip_low is None:

            return self._no_trade(
                "Required 2% dip did not occur."
            )

        dip_index = next(
            index
            for index in range(
                self.OBSERVATION_CANDLES,
                len(normalized),
            )
            if (
                normalized[index]["low_price"]
                is not None
                and normalized[index]["low_price"]
                <= required_dip_price
            )
        )

        confirmation_index = None

        for index in range(
            dip_index + 1,
            len(normalized),
        ):

            candle = normalized[index]

            timestamp = self._timestamp(
                candle
            )

            if timestamp.time() > self.LAST_ENTRY_TIME:
                break

            close_price = candle["close_price"]

            if (
                close_price is None
                or close_price <= opening_price
            ):
                continue

            previous_five = normalized[
                max(0, index - 5):index
            ]

            if len(previous_five) < 5:
                continue

            volumes = [
                c["volume"]
                for c in previous_five
                if c["volume"] is not None
            ]

            if len(volumes) < 5:
                continue

            average_volume = (
                sum(volumes)
                / len(volumes)
            )

            current_volume = candle["volume"]

            if current_volume is None:
                continue

            if current_volume < (
                average_volume
                * self.VOLUME_MULTIPLIER
            ):
                continue

            confirmation_index = index
            break

        if confirmation_index is None:

            return self._no_trade(
                "Dip occurred, but recovery and volume "
                "confirmation did not occur before 14:30."
            )

        if confirmation_index + 1 >= len(normalized):

            return self._not_evaluable(
                "No candle exists after the confirmation candle."
            )

        entry_candle = normalized[
            confirmation_index + 1
        ]

        entry_time = self._timestamp(
            entry_candle
        )

        if entry_time.time() > self.LAST_ENTRY_TIME:
            return self._no_trade(
                "BUY signal occurs after the allowed entry time."
            )

        entry_price = entry_candle["open_price"]

        if entry_price is None or entry_price <= 0:
            return self._not_evaluable(
                "Entry candle has no valid opening price."
            )

        stop_loss_price = max(
            dip_low,
            entry_price
            * (1 - self.MAX_STOP_PERCENT / 100),
        )

        risk = (
            entry_price
            - stop_loss_price
        )

        if risk <= 0:
            return self._not_evaluable(
                "Calculated stop-loss is not below entry."
            )

        target_price = (
            entry_price
            + risk * self.REWARD_RISK
        )

        confirmation_candle = normalized[
            confirmation_index
        ]

        trade_candles = normalized[
            confirmation_index + 1:
        ]

        for candle in trade_candles:

            timestamp = self._timestamp(
                candle
            )

            low_price = candle["low_price"]
            high_price = candle["high_price"]

            if timestamp.time() >= self.FORCE_EXIT_TIME:

                exit_price = (
                    candle["open_price"]
                    if candle["open_price"] is not None
                    else candle["close_price"]
                )

                if exit_price is None:
                    return self._not_evaluable(
                        "Force-exit candle has no valid price."
                    )

                return self._completed_trade(
                    outcome="TIME_EXIT",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=exit_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason=(
                        "Neither stop-loss nor target was "
                        "reached before 15:15."
                    ),
                )

            stop_hit = (
                low_price is not None
                and low_price <= stop_loss_price
            )

            target_hit = (
                high_price is not None
                and high_price >= target_price
            )

            if stop_hit and target_hit:

                return self._completed_trade(
                    outcome="STOP_LOSS",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=stop_loss_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason=(
                        "Both stop-loss and target were "
                        "touched in the same candle. "
                        "Conservative assumption: stop first."
                    ),
                )

            if stop_hit:

                return self._completed_trade(
                    outcome="STOP_LOSS",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=stop_loss_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason="Stop-loss was reached.",
                )

            if target_hit:

                return self._completed_trade(
                    outcome="TARGET",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=target_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason="2R target was reached.",
                )

        return self._not_evaluable(
            "Listing-day candle data ends before the "
            "strategy can determine an exit."
        )

    @staticmethod
    def _normalize_candles(
        candles: list[dict],
    ) -> list[dict]:

        return sorted(
            candles,
            key=lambda candle: IPOListingDayStrategy._timestamp(
                candle
            ),
        )

    @staticmethod
    def _timestamp(
        candle: dict,
    ) -> datetime:

        value = candle["timestamp"]

        if isinstance(value, datetime):
            return value

        return datetime.fromisoformat(
            value
        )

    @staticmethod
    def _no_trade(
        reason: str,
    ) -> IPOListingTradeResult:

        return IPOListingTradeResult(
            outcome="NO_TRADE",
            entry_time=None,
            entry_price=None,
            stop_loss_price=None,
            target_price=None,
            exit_time=None,
            exit_price=None,
            profit_loss=None,
            profit_loss_percent=None,
            dip_low=None,
            dip_percent=None,
            confirmation_time=None,
            confirmation_price=None,
            reason=reason,
        )

    @staticmethod
    def _not_evaluable(
        reason: str,
    ) -> IPOListingTradeResult:

        return IPOListingTradeResult(
            outcome="NOT_EVALUABLE",
            entry_time=None,
            entry_price=None,
            stop_loss_price=None,
            target_price=None,
            exit_time=None,
            exit_price=None,
            profit_loss=None,
            profit_loss_percent=None,
            dip_low=None,
            dip_percent=None,
            confirmation_time=None,
            confirmation_price=None,
            reason=reason,
        )

    @staticmethod
    def _completed_trade(
        outcome: str,
        entry_time: datetime,
        entry_price: float,
        stop_loss_price: float,
        target_price: float,
        exit_time: datetime,
        exit_price: float,
        dip_low: float,
        dip_percent: float,
        confirmation_candle: dict,
        reason: str,
    ) -> IPOListingTradeResult:

        profit_loss = (
            exit_price - entry_price
        )

        profit_loss_percent = (
            profit_loss
            / entry_price
            * 100
        )

        confirmation_time = (
            IPOListingDayStrategy._timestamp(
                confirmation_candle
            )
        )

        return IPOListingTradeResult(
            outcome=outcome,
            entry_time=entry_time.isoformat(
                " "
            ),
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
            exit_time=exit_time.isoformat(
                " "
            ),
            exit_price=exit_price,
            profit_loss=profit_loss,
            profit_loss_percent=profit_loss_percent,
            dip_low=dip_low,
            dip_percent=dip_percent,
            confirmation_time=(
                confirmation_time.isoformat(" ")
            ),
            confirmation_price=(
                confirmation_candle["close_price"]
            ),
            reason=reason,
        )