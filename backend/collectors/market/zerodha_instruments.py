import csv
from io import StringIO

from kiteconnect import KiteConnect

from backend.config.settings import (
    ZERODHA_API_KEY,
    ZERODHA_ACCESS_TOKEN,
)


class ZerodhaInstrumentSource:
    """Download and search Zerodha's instrument master."""

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

    def get_nse_equities(self) -> list[dict]:
        """Return NSE equity instruments."""

        instruments = self.kite.instruments("NSE")

        return [
            instrument
            for instrument in instruments
            if instrument.get("segment") == "NSE"
            and instrument.get("exchange") == "NSE"
        ]

    def find_symbol(self, symbol: str) -> dict | None:
        """Find an NSE instrument by trading symbol."""

        symbol = symbol.upper().strip()

        instruments = self.get_nse_equities()

        for instrument in instruments:
            if instrument.get("tradingsymbol") == symbol:
                return instrument

        return None