import os
from datetime import datetime, timedelta

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect

from backend.collectors.market_data.historical_candle_source import (
    HistoricalCandleSource,
)
from backend.collectors.market_data.angel_one_instrument_resolver import (
    AngelOneInstrumentResolver,
)


load_dotenv()


class AngelOneCandleSource(HistoricalCandleSource):
    """Historical candle source backed by Angel One SmartAPI."""

    def __init__(self):
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

        self.resolver = AngelOneInstrumentResolver()
        self.smart_api = None

    def _login(self):
        totp = pyotp.TOTP(self.totp_secret).now()

        self.smart_api = SmartConnect(
            api_key=self.api_key
        )

        try:
            response = self.smart_api.generateSession(
                self.client_id,
                self.pin,
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

    def fetch(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "ONE_MINUTE",
    ) -> list[dict]:

        self._login()

        instrument = self.resolver.find(
            symbol=symbol,
            exchange="NSE",
        )

        token = instrument["token"]

        start = datetime.strptime(
            listing_date,
            "%Y-%m-%d",
        )

        end = start + timedelta(days=1)

        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": interval,
            "fromdate": start.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "todate": end.strftime(
                "%Y-%m-%d %H:%M"
            ),
        }

        try:
            response = self.smart_api.getCandleData(params)
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

        candles = response.get("data", [])

        return [
            {
                "timestamp": candle[0],
                "open_price": float(candle[1]),
                "high_price": float(candle[2]),
                "low_price": float(candle[3]),
                "close_price": float(candle[4]),
                "volume": int(candle[5]),
            }
            for candle in candles
        ]