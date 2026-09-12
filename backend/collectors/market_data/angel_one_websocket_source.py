from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable

import pyotp
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2


TickHandler = Callable[[dict[str, Any]], None]


class AngelOneWebSocketSource:
    """
    Angel One live market-data WebSocket source.

    Responsibilities:
        - Authenticate with Angel One.
        - Connect SmartWebSocketV2.
        - Subscribe to NSE instrument tokens.
        - Normalize incoming WebSocket messages.
        - Forward normalized ticks to a callback.

    This class does NOT:
        - implement trading strategy
        - place orders
        - make BUY/SELL decisions
        - interact with PaperBroker
    """

    def __init__(
        self,
        on_tick: TickHandler,
    ):
        if not callable(on_tick):
            raise ValueError(
                "on_tick callback is required."
            )

        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.pin = os.getenv("ANGEL_PIN")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        missing = [
            var for var in ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PIN", "ANGEL_TOTP_SECRET"]
            if not os.getenv(var)
        ]
        if missing:
            raise ValueError(
                f"Missing required Angel One credentials in .env: {', '.join(missing)}"
            )

        self.on_tick = on_tick

        self.smart_api: SmartConnect | None = None
        self.websocket: SmartWebSocketV2 | None = None

        self.auth_token: str | None = None
        self.feed_token: str | None = None

        self._subscriptions: list[dict[str, Any]] = []

    def authenticate(self) -> None:
        """Authenticate with Angel One and obtain feed credentials."""

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
                f"Angel One session generation request failed: {exc}"
            ) from exc

        if not response or not isinstance(response, dict):
            raise RuntimeError(
                f"Angel One login returned unexpected response: {response}"
            )

        if not response.get("status"):
            err_msg = response.get("message", "Authentication rejected")
            err_code = response.get("errorcode", "UNKNOWN")
            raise RuntimeError(
                f"Angel One login failed: {err_msg} (Error Code: {err_code})"
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

    def subscribe_nse(
        self,
        tokens: list[str],
    ) -> None:
        """
        Register NSE tokens for live LTP data.

        Angel One exchangeType:
            1 = NSE
        """

        if not tokens:
            raise ValueError(
                "At least one NSE token is required."
            )

        normalized_tokens = []

        for token in tokens:
            token = str(token).strip()

            if token and token not in normalized_tokens:
                normalized_tokens.append(token)

        if not normalized_tokens:
            raise ValueError(
                "No valid NSE tokens were supplied."
            )

        self._subscriptions = [
            {
                "exchangeType": 1,
                "tokens": normalized_tokens,
            }
        ]

    def _build_websocket(self) -> SmartWebSocketV2:
        if not self.auth_token:
            raise RuntimeError(
                "Angel One authentication is required."
            )

        if not self.feed_token:
            raise RuntimeError(
                "Angel One feed token is unavailable."
            )

        websocket = SmartWebSocketV2(
            self.auth_token,
            self.api_key,
            self.client_id,
            self.feed_token,
        )

        websocket.on_data = self._on_data
        websocket.on_open = self._on_open
        websocket.on_error = self._on_error
        websocket.on_close = self._on_close

        return websocket

    def connect(self) -> None:
        """
        Authenticate if necessary and start the WebSocket.

        SmartWebSocketV2.connect() blocks while the socket is active.
        """

        if self.smart_api is None:
            self.authenticate()

        self.websocket = self._build_websocket()

        self.websocket.connect()

    def _on_open(self, wsapp) -> None:
        """Subscribe once the WebSocket connection is established."""

        if not self._subscriptions:
            return

        correlation_id = "ipo_live_market"
        mode = 1  # LTP

        self.websocket.subscribe(
            correlation_id,
            mode,
            self._subscriptions,
        )

    def _on_data(
        self,
        wsapp,
        message,
    ) -> None:
        """Normalize and forward an incoming Angel One tick."""

        tick = self._normalize_message(message)

        if tick is None:
            return

        self.on_tick(tick)

    @staticmethod
    def _on_error(
        wsapp,
        error,
    ) -> None:
        """WebSocket error callback."""
        import sys
        sys.stderr.write(f"\n[ERROR] Angel One SmartWebSocketV2 error: {error}\n")
        sys.stderr.flush()

    @staticmethod
    def _on_close(
        wsapp,
    ) -> None:
        """WebSocket close callback."""

        print(
            "Angel One WebSocket closed."
        )

    @staticmethod
    def _normalize_message(
        message,
    ) -> dict[str, Any] | None:
        """
        Normalize SmartWebSocketV2 data.

        SmartAPI WebSocket messages are normally dictionaries.

        The SDK payload contains token, exchange information,
        LTP and exchange timestamp. We retain the raw message
        for debugging and future fields.
        """

        if not isinstance(message, dict):
            return None

        token = message.get("token")

        if token is None:
            return None

        ltp = message.get("last_traded_price")
        is_paise = False

        if ltp is not None:
            is_paise = True
        else:
            ltp = message.get("ltp")

        if ltp is None:
            return None

        try:
            price = float(ltp)
        except (TypeError, ValueError):
            return None

        if price <= 0:
            return None

        # SmartWebSocketV2 delivers LTP in paise in binary data packets (e.g. 5567 paise -> Rs. 55.67)
        if is_paise and (isinstance(ltp, int) or price > 1000):
            price = round(price / 100.0, 2)

        timestamp = (
            message.get("exchange_timestamp")
            or message.get("timestamp")
        )

        normalized_timestamp = (
            AngelOneWebSocketSource._parse_timestamp(
                timestamp
            )
        )

        if normalized_timestamp is None:
            normalized_timestamp = datetime.now()

        volume = (
            message.get("volume_trade_for_the_day")
            or message.get("volume")
            or 0
        )

        try:
            volume = int(volume)
        except (TypeError, ValueError):
            volume = 0

        return {
            "token": str(token),
            "symbol": message.get(
                "symbol",
                str(token),
            ),
            "exchange": message.get(
                "exchange_type",
                "NSE",
            ),
            "timestamp": normalized_timestamp,
            "price": price,
            "volume": volume,
            "raw": message,
        }

    @staticmethod
    def _parse_timestamp(
        value,
    ) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(
                    value / 1000
                )
            except (ValueError, OSError):
                return None

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(
                    value
                )
            except ValueError:
                return None

        return None

    def close(self) -> None:
        """Close the active WebSocket connection."""

        if self.websocket is None:
            return

        close = getattr(
            self.websocket,
            "close_connection",
            None,
        )

        if callable(close):
            close()

        self.websocket = None