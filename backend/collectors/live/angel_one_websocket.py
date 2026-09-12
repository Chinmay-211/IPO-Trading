from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Any

import pyotp
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2


class AngelOneWebSocket:
    """
    Angel One live market-data connection.

    This class only receives market data.
    It does not place orders.
    """

    def __init__(
        self,
        on_tick: Callable[[dict[str, Any]], None],
    ):
        if on_tick is None:
            raise ValueError("on_tick callback is required.")

        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.pin = os.getenv("ANGEL_PIN")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        if not all([
            self.api_key,
            self.client_id,
            self.pin,
            self.totp_secret,
        ]):
            raise ValueError(
                "Angel One credentials are missing from .env"
            )

        self.on_tick = on_tick

        self.smart_api = None
        self.websocket = None

        self.auth_token = None
        self.feed_token = None

    def authenticate(self) -> None:
        """
        Authenticate with Angel One and obtain feed credentials.
        """

        totp = pyotp.TOTP(
            self.totp_secret
        ).now()

        self.smart_api = SmartConnect(
            api_key=self.api_key
        )

        try:
            response = self.smart_api.generateSession(
                self.client_id,
                self.pin,
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

        if not self.auth_token or not self.feed_token:
            raise RuntimeError(
                "Angel One authentication did not return "
                "WebSocket credentials."
            )

    def connect(
        self,
        subscriptions: list[dict[str, Any]],
        correlation_id: str = "ipo_live",
        mode: int = 1,
    ) -> None:
        """
        Connect and subscribe to Angel One live market data.

        subscriptions format:

        [
            {
                "exchangeType": 1,
                "tokens": ["765356"]
            }
        ]

        exchangeType 1 = NSE.
        mode 1 = LTP.
        """

        if not subscriptions:
            raise ValueError(
                "At least one subscription is required."
            )

        if self.auth_token is None:
            self.authenticate()

        self.websocket = SmartWebSocketV2(
            self.auth_token,
            self.api_key,
            self.client_id,
            self.feed_token,
        )

        def on_open(wsapp):
            self.websocket.subscribe(
                correlation_id,
                mode,
                subscriptions,
            )

        def on_data(wsapp, message):
            tick = self._normalize_tick(message)

            if tick is not None:
                self.on_tick(tick)

        def on_error(wsapp, error):
            raise RuntimeError(
                f"Angel One WebSocket error: {error}"
            )

        def on_close(wsapp):
            pass

        self.websocket.on_open = on_open
        self.websocket.on_data = on_data
        self.websocket.on_error = on_error
        self.websocket.on_close = on_close

        self.websocket.connect()

    @staticmethod
    def _normalize_tick(
        message: Any,
    ) -> dict[str, Any] | None:
        """
        Normalize Angel One WebSocket LTP messages.

        Angel One may return fields in either raw numeric/string
        form depending on SDK/message version.
        """

        if not isinstance(message, dict):
            return None

        token = (
            message.get("token")
            or message.get("symboltoken")
        )

        price = (
            message.get("last_traded_price")
            or message.get("last_traded_price")
        )

        if token is None or price is None:
            return None

        try:
            price = float(price)

            # Angel One WebSocket LTP values are commonly
            # represented in paise.
            if price > 100000:
                price /= 100.0

        except (TypeError, ValueError):
            return None

        timestamp = message.get(
            "exchange_timestamp"
        )

        if timestamp is None:
            timestamp = datetime.now()

        elif isinstance(timestamp, (int, float)):
            # Angel One timestamps are commonly milliseconds.
            timestamp = datetime.fromtimestamp(
                timestamp / 1000
            )

        elif isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(
                    timestamp
                )
            except ValueError:
                timestamp = datetime.now()

        volume = message.get(
            "last_traded_quantity",
            0,
        )

        try:
            volume = int(volume or 0)
        except (TypeError, ValueError):
            volume = 0

        return {
            "token": str(token),
            "price": price,
            "timestamp": timestamp,
            "volume": volume,
            "raw": message,
        }