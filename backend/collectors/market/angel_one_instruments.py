import json
import os
import time

import requests

from backend.config.settings import (
    ANGEL_API_KEY,
)


INSTRUMENT_URL = (
    "https://margincalculator.angelone.in/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)


class AngelOneInstrumentSource:
    """Download and search Angel One instruments."""

    def __init__(
        self,
        cache_path: str | None = None,
        cache_ttl_hours: int = 24,
    ):
        if not ANGEL_API_KEY:
            raise RuntimeError(
                "ANGEL_API_KEY is not configured."
            )

        self._instruments = None
        self.cache_path = cache_path or os.path.join(
            "data", "cache", "angel_one_instruments.json"
        )
        self.cache_ttl_seconds = cache_ttl_hours * 3600

    def _load_instruments(self):
        if self._instruments is not None:
            return

        # 1. Try valid cache from disk
        if os.path.exists(self.cache_path):
            mtime = os.path.getmtime(self.cache_path)
            if (time.time() - mtime) < self.cache_ttl_seconds:
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self._instruments = data
                            return
                except Exception:
                    pass

        # 2. Attempt remote download
        try:
            response = requests.get(
                INSTRUMENT_URL,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            self._instruments = data

            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return
        except Exception:
            # 3. Fallback to existing stale cache if network fails
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self._instruments = data
                            return
                except Exception:
                    pass
            raise

    def get_nse_equities(self) -> list[dict]:
        """Return Angel One NSE equity instruments."""

        self._load_instruments()

        return [
            instrument
            for instrument in self._instruments
            if instrument.get("exch_seg") == "NSE"
            and instrument.get("instrumenttype") == ""
            and instrument.get("symbol", "").endswith("-EQ")
        ]

    def find_symbol(
    self,
    symbol: str,
) -> dict | None:
        """Find an NSE equity by base trading symbol."""

        self._load_instruments()

        symbol = symbol.upper().strip()

        # 1. Exact NSE match.
        for instrument in self._instruments:
            if (
                instrument.get("exch_seg") == "NSE"
                and instrument.get("symbol", "").upper()
                == symbol
            ):
                return instrument

        # 2. Common NSE equity series.
        for suffix in ("-EQ", "-ST"):
            target = f"{symbol}{suffix}"

            for instrument in self._instruments:
                if (
                    instrument.get("exch_seg") == "NSE"
                    and instrument.get("symbol", "").upper()
                    == target
                ):
                    return instrument

        return None