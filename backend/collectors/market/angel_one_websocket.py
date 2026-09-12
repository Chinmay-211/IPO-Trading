from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import pyotp
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from backend.config.settings import (
    ANGEL_API_KEY,
    ANGEL_CLIENT_ID,
    ANGEL_PIN,
    ANGEL_TOTP_SECRET,
)
from backend.collectors.market.angel_one_live_candle_builder import (
    AngelOneLiveCandleBuilder,
    LiveCandle,
)


class AngelOneWebSocket:
    """
    Angel One live market-data WebSocket.

    Responsibilities:
        - Authenticate with Angel One.
        - Open the WebSocket.
        - Subscribe to instrument tokens.
        - Receive live ticks.
        - Convert ticks into 1-minute candles.

    This class does NOT:
        - evaluate IPO screening rules
        - make BUY/SELL decisions
        - place orders
        - access the broker execution layer
    """

    def __init__(
        self,
        candle_builder: AngelOneLiveCandleBuilder | None = None,
        on_candle: Callable[[LiveCandle], None] | None = None,
    ):
        self.candle_builder = (
            candle_builder
            if candle_builder is not None
            else AngelOneLiveCandleBuilder()
        )

        self.on_candle = on_candle

        self.smart_api: SmartConnect | None = None
        self.websocket: SmartWebSocketV2 | None = None

        self.auth_token: str | None = None
        self.feed_token: str | None = None

        self.connected = False
        self.subscribed = False

    def authenticate(self) -> None:
        """Authenticate with Angel One and obtain WebSocket tokens."""

        required = {
            "ANGEL_API_KEY": ANGEL_API_KEY,
            "ANGEL_CLIENT_ID": ANGEL_CLIENT_ID,
            "ANGEL_PIN": ANGEL_PIN,
            "ANGEL_TOTP_SECRET": ANGEL_TOTP_SECRET,
        }

        missing = [
            name
            for name, value in required.items()
            if not value
        ]

        if missing:
            raise RuntimeError(
                "Missing Angel One configuration: "
                + ", ".join(missing)
            )

        totp = pyotp.TOTP(
            ANGEL_TOTP_SECRET
        ).now()

        self.smart_api = SmartConnect(
            api_key=ANGEL_API_KEY
        )

        try:
            response = self.smart_api.generateSession(
                ANGEL_CLIENT_ID,
                ANGEL_PIN,
                totp,
            )
        except Exception as exc:
            raise RuntimeError(
                "Angel One authentication failed."
            ) from exc

        if not response.get("status"):
            raise RuntimeError(
                "Angel One authentication was rejected."
            )

        data = response.get("data") or {}

        self.auth_token = data.get("jwtToken")
        self.feed_token = data.get("feedToken")

        if not self.auth_token:
            raise RuntimeError(
                "Angel One authentication did not return jwtToken."
            )

        if not self.feed_token:
            raise RuntimeError(
                "Angel One authentication did not return feedToken."
            )

    def connect(self) -> None:
        """Create and connect the Angel One WebSocket."""

        if not self.auth_token or not self.feed_token:
            self.authenticate()

        self.websocket = SmartWebSocketV2(
            self.auth_token,
            ANGEL_API_KEY,
            ANGEL_CLIENT_ID,
            self.feed_token,
        )

        self.websocket.on_open = self._on_open
        self.websocket.on_data = self._on_data
        self.websocket.on_error = self._on_error
        self.websocket.on_close = self._on_close

        self.websocket.connect()

    def subscribe(
        self,
        correlation_id: str,
        exchange_type: int,
        tokens: list[str],
        mode: int = 1,
    ) -> None:
        """
        Subscribe to Angel One instrument tokens.

        exchange_type:
            1 = NSE

        mode:
            1 = LTP
            2 = Quote
            3 = Snap Quote
        """

        if self.websocket is None:
            raise RuntimeError(
                "WebSocket is not initialized."
            )

        if not tokens:
            raise ValueError(
                "At least one instrument token is required."
            )

        token_list = [
            {
                "exchangeType": exchange_type,
                "tokens": [
                    str(token)
                    for token in tokens
                ],
            }
        ]

        self.websocket.subscribe(
            correlation_id,
            mode,
            token_list,
        )

        self.subscribed = True

    def _on_open(self, wsapp) -> None:
        self.connected = True

        print(
            "Angel One WebSocket connected."
        )

    def _on_data(
        self,
        wsapp,
        message: Any,
    ) -> None:
        """
        Process one WebSocket tick.

        Angel One WebSocket messages can vary by mode.
        The method therefore validates the fields before
        attempting candle construction.
        """

        if not isinstance(message, dict):
            return

        token = (
            message.get("token")
            or message.get("symboltoken")
        )

        if token is None:
            return

        price = self._extract_price(message)

        if price is None:
            return

        timestamp = self._extract_timestamp(
            message
        )

        if timestamp is None:
            timestamp = datetime.now()

        volume = self._extract_volume(
            message
        )

        candle = self.candle_builder.update(
            symbol=str(token),
            price=price,
            timestamp=timestamp,
            volume=volume,
        )

        if self.on_candle is not None:
            self.on_candle(candle)

    @staticmethod
    def _extract_price(
        message: dict[str, Any],
    ) -> float | None:
        """
        Extract LTP from Angel One message.

        Angel One commonly returns LTP in paise
        through `last_traded_price`.
        """

        value = message.get(
            "last_traded_price"
        )

        if value is None:
            value = message.get(
                "lastTradedPrice"
            )

        if value is None:
            value = message.get("ltp")

        if value is None:
            return None

        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        # Angel One WebSocket LTP is commonly
        # represented in paise.
        if value > 100000:
            value /= 100

        return value

    @staticmethod
    def _extract_volume(
        message: dict[str, Any],
    ) -> int | None:

        value = (
            message.get("volume_trade_for_the_day")
            or message.get("volume")
        )

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_timestamp(
        message: dict[str, Any],
    ) -> datetime | None:

        value = (
            message.get("exchange_timestamp")
            or message.get("exchangeTimestamp")
        )

        if value is None:
            return None

        try:
            value = int(value)

            # Angel One timestamps are generally
            # Unix timestamps in milliseconds.
            if value > 10_000_000_000:
                value /= 1000

            return datetime.fromtimestamp(
                value
            )

        except (TypeError, ValueError, OSError):
            return None

    def _on_error(
        self,
        wsapp,
        error: Any,
    ) -> None:
        self.connected = False

        print(
            "Angel One WebSocket error:",
            error,
        )

    def _on_close(
        self,
        wsapp,
    ) -> None:
        self.connected = False
        self.subscribed = False

        print(
            "Angel One WebSocket closed."
        )

    def close(self) -> None:
        """Close the WebSocket connection."""

        if self.websocket is None:
            return

        close_method = getattr(
            self.websocket,
            "close",
            None,
        )

        if callable(close_method):
            close_method()

        self.connected = False
        self.subscribed = False

    def get_candles(
        self,
        symbol: str | None = None,
    ) -> list[LiveCandle]:

        return self.candle_builder.get_all(
            symbol=symbol
        )

    def reset(self) -> None:
        self.candle_builder.reset()