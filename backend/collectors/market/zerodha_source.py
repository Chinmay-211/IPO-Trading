from datetime import datetime
from typing import Any

from kiteconnect import KiteConnect

from backend.collectors.market.base import MarketDataSource
from backend.config.settings import (
    ZERODHA_API_KEY,
    ZERODHA_ACCESS_TOKEN,
)


class ZerodhaDataSource(MarketDataSource):
    """Zerodha Kite historical market-data source."""

    def __init__(self):
        if not ZERODHA_API_KEY:
            raise RuntimeError(
                "ZERODHA_API_KEY is not configured."
            )

        if not ZERODHA_ACCESS_TOKEN:
            raise RuntimeError(
                "ZERODHA_ACCESS_TOKEN is not configured."
            )

        self.kite = KiteConnect(
            api_key=ZERODHA_API_KEY
        )

        self.kite.set_access_token(
            ZERODHA_ACCESS_TOKEN
        )

    def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "minute",
    ) -> list[dict[str, Any]]:
        """
        Fetch historical candles from Zerodha.

        `symbol` is currently expected to be the
        Zerodha instrument token.
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required")

        candles = self.kite.historical_data(
            instrument_token=int(symbol),
            from_date=start,
            to_date=end,
            interval=interval,
            continuous=False,
            oi=False,
        )

        normalized = []

        for candle in candles:
            normalized.append({
                "timestamp": candle["date"],
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle.get("volume"),
                "source": "zerodha",
            })

        return normalized