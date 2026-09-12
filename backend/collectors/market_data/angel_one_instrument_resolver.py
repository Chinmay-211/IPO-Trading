import json
import os
import time

import requests


INSTRUMENT_URL = (
    "https://margincalculator.angelone.in/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)


class AngelOneInstrumentResolver:
    """Resolves NSE/BSE symbols to Angel One instrument tokens."""

    def __init__(
        self,
        cache_path: str | None = None,
        cache_ttl_hours: int = 24,
    ):
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
                timeout=3,
            )
            response.raise_for_status()
            data = response.json()
            self._instruments = data

            # Save fresh cache to disk
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return
        except Exception:
            # 3. Fallback to existing stale cache if network/server fails
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

    def find(
        self,
        symbol: str,
        exchange: str = "NSE",
    ) -> dict:
        self._load_instruments()

        symbol = symbol.upper().strip()

        # First try exact match.
        for instrument in self._instruments:
            if (
                instrument.get("exch_seg") == exchange
                and instrument.get("symbol", "").upper() == symbol
            ):
                return instrument

        # IPO symbols may be stored without the Angel One
        # security suffix, e.g. HORIZONIND -> HORIZONIND-EQ.
        candidates = [
            instrument
            for instrument in self._instruments
            if (
                instrument.get("exch_seg") == exchange
                and instrument.get("instrumenttype") == ""
                and instrument.get("symbol", "").upper()
                in {
                    f"{symbol}-EQ",
                    f"{symbol}-ST",
                }
            )
        ]

        if not candidates:
            raise ValueError(
                f"Instrument not found: "
                f"{exchange}:{symbol}"
            )

        # Prefer normal equity when both EQ and ST exist.
        for instrument in candidates:
            if instrument.get("symbol", "").upper() == f"{symbol}-EQ":
                return instrument

        return candidates[0]