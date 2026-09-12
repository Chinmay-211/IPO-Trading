from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


class MarketSessionService:
    """
    Determines whether the Indian equity market is open.

    NSE regular session:
        09:15 - 15:30 IST

    This service only answers session-state questions.
    It does not place orders or make strategy decisions.
    """

    IST = ZoneInfo("Asia/Kolkata")

    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    IPO_LISTING_OPEN = time(10, 0)

    def __init__(
        self,
        market_open: time | None = None,
        market_close: time | None = None,
    ):
        self.market_open = (
            market_open
            if market_open is not None
            else self.MARKET_OPEN
        )

        self.market_close = (
            market_close
            if market_close is not None
            else self.MARKET_CLOSE
        )

    @classmethod
    def for_ipo_listing(
        cls,
        listing_open: time = time(10, 0),
        market_close: time = time(15, 30),
    ) -> MarketSessionService:
        """Create a session service configured for listing-day continuous trading (10:00 - 15:30 IST)."""
        return cls(
            market_open=listing_open,
            market_close=market_close,
        )

    @classmethod
    def _to_ist(
        cls,
        timestamp: datetime,
    ) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(
                tzinfo=cls.IST
            )

        return timestamp.astimezone(cls.IST)

    def is_market_open(
        self,
        timestamp: datetime,
    ) -> bool:
        """
        Return True when the timestamp falls inside
        the regular NSE equity trading session.

        Note:
            This first implementation checks only the
            daily session window. Exchange holidays are
            intentionally handled separately later.
        """

        if not isinstance(timestamp, datetime):
            raise TypeError(
                "timestamp must be a datetime."
            )

        timestamp = self._to_ist(timestamp)

        current_time = timestamp.time()

        return (
            self.market_open
            <= current_time
            < self.market_close
        )

    def is_before_market_open(
        self,
        timestamp: datetime,
    ) -> bool:
        if not isinstance(timestamp, datetime):
            raise TypeError(
                "timestamp must be a datetime."
            )

        timestamp = self._to_ist(timestamp)

        return (
            timestamp.time()
            < self.market_open
        )

    def is_after_market_close(
        self,
        timestamp: datetime,
    ) -> bool:
        if not isinstance(timestamp, datetime):
            raise TypeError(
                "timestamp must be a datetime."
            )

        timestamp = self._to_ist(timestamp)

        return (
            timestamp.time()
            >= self.market_close
        )

    def get_session_state(
        self,
        timestamp: datetime,
    ) -> str:
        """
        Return one of:

            PRE_OPEN
            OPEN
            CLOSED
        """

        if self.is_before_market_open(
            timestamp
        ):
            return "PRE_OPEN"

        if self.is_market_open(
            timestamp
        ):
            return "OPEN"

        return "CLOSED"