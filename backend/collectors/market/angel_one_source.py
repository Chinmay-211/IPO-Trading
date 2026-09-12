from datetime import datetime
from typing import Any

import pyotp
from SmartApi import SmartConnect

from backend.collectors.market.base import MarketDataSource
from backend.config.settings import (
    ANGEL_API_KEY,
    ANGEL_CLIENT_ID,
    ANGEL_PIN,
    ANGEL_TOTP_SECRET,
)


class AngelOneDataSource(MarketDataSource):
    """Angel One SmartAPI historical market-data source."""

    def __init__(self):
        if not ANGEL_API_KEY:
            raise RuntimeError(
                "ANGEL_API_KEY is not configured."
            )

        if not ANGEL_CLIENT_ID:
            raise RuntimeError(
                "ANGEL_CLIENT_ID is not configured."
            )

        if not ANGEL_PIN:
            raise RuntimeError(
                "ANGEL_PIN is not configured."
            )

        if not ANGEL_TOTP_SECRET:
            raise RuntimeError(
                "ANGEL_TOTP_SECRET is not configured."
            )

        self.smart_api = SmartConnect(
            api_key=ANGEL_API_KEY
        )

        self._login()

    def _login(self):
        totp = pyotp.TOTP(
            ANGEL_TOTP_SECRET
        ).now()

        try:
            response = self.smart_api.generateSession(
                ANGEL_CLIENT_ID,
                ANGEL_PIN,
                totp,
            )
        except Exception:
            raise RuntimeError(
                "Angel One login could not be completed. "
                "The provider may be rate-limiting requests."
            ) from None

        if not response.get("status"):
            raise RuntimeError(
                "Angel One login failed. Check the provider response "
                "and account configuration."
            )

    @staticmethod
    def _normalize_interval(interval: str) -> str:
        mapping = {
            "1m": "ONE_MINUTE",
            "3m": "THREE_MINUTE",
            "5m": "FIVE_MINUTE",
            "10m": "TEN_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "30m": "THIRTY_MINUTE",
            "1h": "ONE_HOUR",
            "1d": "ONE_DAY",
            "minute": "ONE_MINUTE",
            "day": "ONE_DAY",
        }

        normalized = mapping.get(interval.lower())

        if normalized is None:
            raise ValueError(
                f"Unsupported Angel One interval: {interval}"
            )

        return normalized

    def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> list[dict[str, Any]]:
        """
        Fetch historical candles from Angel One.

        `symbol` is expected to be the Angel One
        instrument token.
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required")

        angel_interval = self._normalize_interval(
            interval
        )

        params = {
            "exchange": "NSE",
            "symboltoken": symbol.strip(),
            "interval": angel_interval,
            "fromdate": start.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "todate": end.strftime(
                "%Y-%m-%d %H:%M"
            ),
        }

        try:
            response = self.smart_api.getCandleData(
                params
            )
        except Exception:
            raise RuntimeError(
                "Angel One historical data request could not be "
                "completed. The provider may be rate-limiting requests."
            ) from None

        if not response.get("status"):
            raise RuntimeError(
                "Angel One historical data request was rejected by "
                "the provider."
            )

        candles = response.get("data") or []

        normalized = []

        for candle in candles:
            normalized.append({
                "timestamp": datetime.fromisoformat(
                    candle[0]
                ),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": (
                    int(candle[5])
                    if candle[5] is not None
                    else None
                ),
                "source": "angel_one",
            })

        return normalized