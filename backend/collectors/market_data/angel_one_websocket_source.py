from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

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
        exchange_type: int = 1,
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

        # Support exchangeType mapping (1: NSE, 3: BSE)
        exch = int(exchange_type) if exchange_type in (1, 3) else 1
        
        # Merge with existing subscriptions so previous tokens aren't lost
        current_tokens = []
        if self._subscriptions and isinstance(self._subscriptions, list):
            for sub in self._subscriptions:
                if sub.get("exchangeType") == exch:
                    current_tokens.extend(sub.get("tokens", []))

        merged = list(dict.fromkeys(current_tokens + normalized_tokens))
        # Keep other exchange subscriptions intact
        other_subs = [s for s in self._subscriptions if s.get("exchangeType") != exch]
        self._subscriptions = other_subs + [
            {
                "exchangeType": exch,
                "tokens": merged,
            }
        ]

        # If WebSocket is actively running, send subscribe frame immediately
        if self.websocket is not None:
            try:
                # ponytail: correlationID must be <= 10 alphanumeric chars per Angel One SmartStream spec
                self.websocket.subscribe(
                    "ipo01",
                    2,  # mode 2 (Quote: LTP + OHLC + Volume)
                    [{"exchangeType": exch, "tokens": normalized_tokens}],
                )
            except Exception as exc:
                import sys
                sys.stderr.write(f"[ERROR] Live WebSocket subscribe failed for {normalized_tokens}: {exc}\n")

    def unsubscribe_nse(
        self,
        tokens: list[str],
        exchange_type: int = 1,
    ) -> None:
        """Unregister tokens from live WebSocket data."""
        if not tokens or not self._subscriptions:
            return

        exch = int(exchange_type) if exchange_type in (1, 3) else 1
        to_remove = {str(t).strip() for t in tokens if str(t).strip()}
        for sub in self._subscriptions:
            if sub.get("exchangeType") == exch:
                sub["tokens"] = [t for t in sub.get("tokens", []) if t not in to_remove]

        if self.websocket is not None:
            try:
                unsubscribe = getattr(self.websocket, "unsubscribe", None)
                if callable(unsubscribe):
                    unsubscribe(
                        "ipo01",
                        2,
                        [{"exchangeType": exch, "tokens": list(to_remove)}],
                    )
            except Exception:
                pass

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

        # ponytail: hook control & text messages so server-side warnings, errors, or rejects are visible
        def _on_control(msg):
            import sys
            sys.stderr.write(f"[AngelOneWS Control] {msg}\n")
            sys.stderr.flush()

        def _on_text(wsapp, msg):
            import sys
            sys.stderr.write(f"[AngelOneWS Message] {msg}\n")
            sys.stderr.flush()

        websocket.on_control_message = _on_control
        websocket.on_message = _on_text

        return websocket

    def connect(self) -> None:
        """
        Authenticate if necessary and start the WebSocket.

        SmartWebSocketV2.connect() blocks while the socket is active.
        On disconnect, the reconnect manager retries with backoff.
        """
        from backend.services.websocket_reconnect_manager import WebSocketReconnectManager

        # ponytail: one reconnect manager per connect() call; unlimited retries
        # during market hours. Ceiling: add a market-hours gate to stop retrying
        # after 15:30 IST.
        self._reconnect_mgr = WebSocketReconnectManager(
            base_delay=2.0,
            max_delay=30.0,
            max_retries=999,
        )
        self._closed = False

        if self.smart_api is None:
            self.authenticate()

        self._do_connect()

    def _do_connect(self) -> None:
        """Build and start the WebSocket (called on first connect and each reconnect)."""
        self.websocket = self._build_websocket()
        self.websocket.connect()  # blocks until the socket closes

    def _on_open(self, wsapp) -> None:
        """Subscribe once the WebSocket connection is established."""
        if hasattr(self, "_reconnect_mgr"):
            self._reconnect_mgr.on_connected()

        if not self._subscriptions:
            return

        # ponytail: correlation_id <= 10 alphanumeric chars per Angel One SmartStream spec
        correlation_id = "ipo01"
        # mode=2 (Quote) provides LTP, OHLC, and Volume without the depth/circuit limitations of mode 3
        mode = 2

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

    def _on_error(
        self,
        wsapp,
        error,
    ) -> None:
        """WebSocket error — log and let _on_close handle reconnect."""
        import sys
        sys.stderr.write(f"\n[ERROR] Angel One SmartWebSocketV2 error: {error}\n")
        sys.stderr.flush()

    def _on_close(
        self,
        wsapp,
    ) -> None:
        """WebSocket closed — reconnect with exponential backoff in a daemon thread."""
        import sys
        import threading

        if getattr(self, "_closed", True):
            return  # explicit close() called — don't reconnect

        sys.stderr.write("\n[WARN] Angel One WebSocket closed. Scheduling reconnect...\n")
        sys.stderr.flush()

        def _reconnect_loop():
            mgr = getattr(self, "_reconnect_mgr", None)
            if mgr is None:
                return

            while not getattr(self, "_closed", True):
                delay = mgr.get_backoff_delay()
                sys.stderr.write(
                    f"[RECONNECT] Waiting {delay:.1f}s before reconnect "
                    f"(attempt {mgr.retry_count + 1}/{mgr.max_retries})...\n"
                )
                sys.stderr.flush()
                import time as _time
                _time.sleep(delay)

                try:
                    # Re-authenticate: JWT and feedToken expire; always refresh.
                    self.authenticate()
                    self._do_connect()
                    mgr.total_reconnects += 1
                    mgr.on_connected()
                    sys.stderr.write("[RECONNECT] Angel One WebSocket reconnected.\n")
                    sys.stderr.flush()
                    return  # _do_connect blocks until next disconnect
                except Exception as exc:
                    mgr.retry_count += 1
                    mgr.last_error = str(exc)
                    sys.stderr.write(f"[RECONNECT] Attempt failed: {exc}\n")
                    sys.stderr.flush()

        threading.Thread(
            target=_reconnect_loop,
            name="AngelOneWSReconnect",
            daemon=True,
        ).start()



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
            normalized_timestamp = datetime.now(tz=IST)

        volume = (
            message.get("volume_trade_for_the_day")
            or message.get("volume")
            or 0
        )

        try:
            volume = int(volume)
        except (TypeError, ValueError):
            volume = 0

        result: dict[str, Any] = {
            "token": str(token),
            "timestamp": normalized_timestamp,
            "price": price,
            "volume": volume,
            "raw": message,
        }

        # Only include "symbol" when the exchange actually sends one.
        # Never fall back to the token number — that breaks feeder resolution.
        raw_symbol = message.get("symbol")
        if raw_symbol and str(raw_symbol).strip():
            result["symbol"] = str(raw_symbol).strip().upper()

        exchange = message.get("exchange_type")
        if exchange:
            result["exchange"] = exchange

        return result

    @staticmethod
    def _parse_timestamp(
        value,
    ) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=IST)
            return value.astimezone(IST)

        if isinstance(value, (int, float)):
            try:
                # Millisecond epoch timestamp from exchange converted to IST
                sec = value / 1000 if value > 10_000_000_000 else value
                return datetime.fromtimestamp(sec, tz=IST)
            except (ValueError, OSError):
                return None

        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=IST)
                return dt.astimezone(IST)
            except ValueError:
                return None

        return None

    def close(self) -> None:
        """Close the active WebSocket connection (no reconnect)."""

        self._closed = True  # stop reconnect loop

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