from datetime import datetime
from typing import Any

import requests

from backend.collectors.market.base import MarketDataSource
from backend.config.settings import PAYTM_MONEY_JWT


class PaytmMoneyDataSource(MarketDataSource):
    """Paytm Money historical market-data source."""

    URL = "https://developer.paytmmoney.com/data/v1/price-charts/sym"

    def __init__(self):
        if not PAYTM_MONEY_JWT:
            raise RuntimeError(
                "PAYTM_MONEY_JWT is not configured. "
                "Add it to the .env file."
            )

        self.session = requests.Session()

        self.session.headers.update({
            "x-jwt-token": PAYTM_MONEY_JWT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> list[dict[str, Any]]:

        if interval != "1m":
            raise ValueError(
                "Initial implementation supports only 1m candles."
            )

        payload = {
            "cont": "false",
            "exchange": "NSE",
            "fromDate": start.strftime("%Y-%m-%d"),
            "instType": "ES",
            "interval": "MINUTE",
            "symbol": symbol,
            "toDate": end.strftime("%Y-%m-%d"),
        }

        response = self.session.post(
            self.URL,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        return self._normalize_response(data)

    @staticmethod
    def _normalize_response(
        data: Any,
    ) -> list[dict[str, Any]]:
        """
        Normalize the provider response.

        The exact response structure will be confirmed
        using the first authenticated request.
        """

        if isinstance(data, list):
            raw_candles = data
        elif isinstance(data, dict):
            raw_candles = data.get("data", [])
        else:
            raise ValueError(
                "Unexpected Paytm Money response format."
            )

        candles = []

        for row in raw_candles:
            if not isinstance(row, dict):
                continue

            timestamp = (
                row.get("timestamp")
                or row.get("Date & Time")
                or row.get("dateTime")
            )

            open_price = row.get("open") or row.get("Open")
            high_price = row.get("high") or row.get("High")
            low_price = row.get("low") or row.get("Low")
            close_price = row.get("close") or row.get("Close")
            volume = row.get("volume") or row.get("Volume")

            if timestamp is None:
                continue

            candles.append({
                "timestamp": timestamp,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "source": "paytm_money",
            })

        return candles