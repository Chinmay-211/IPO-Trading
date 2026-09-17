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
        # Common IPO discovery abbreviation aliases
        _ALIASES = {
            "ASSETRECON": "ARCIL",
            "KARAMTARAE": "KARAMTARA",
            "MANIPALPAY": "MPIMANIPAL",
            "RENTOMOJOP": "RENTOMOJO",
        }
        symbol = _ALIASES.get(symbol, symbol)

        # Angel One instrument type suffixes used for equities / IPOs.
        # ponytail: cover common IPO suffix variants in one pass.
        # Ceiling: pull this list from the instrument master metadata.
        _SUFFIXES = ("-EQ", "-SM", "-ST", "-BE", "-BZ", "-N1", "-N2")

        def _search(exch: str) -> dict | None:
            # 1. Exact match on the raw symbol.
            for inst in self._instruments:
                if (
                    inst.get("exch_seg") == exch
                    and inst.get("symbol", "").upper() == symbol
                ):
                    return inst

            # 2. Suffix variants — prefer -EQ, then take first match.
            candidates = [
                inst for inst in self._instruments
                if (
                    inst.get("exch_seg") == exch
                    and inst.get("symbol", "").upper() in {
                        f"{symbol}{sfx}" for sfx in _SUFFIXES
                    }
                )
            ]

            if not candidates:
                return None

            # Prefer normal equity.
            for inst in candidates:
                if inst.get("symbol", "").upper() == f"{symbol}-EQ":
                    return inst

            return candidates[0]

        result = _search(exchange)
        if result is not None:
            return result

        # Fallback: try the other exchange (BSE ↔ NSE).
        other = "BSE" if exchange == "NSE" else "NSE"
        result = _search(other)
        if result is not None:
            return result

        raise ValueError(
            f"Instrument not found: {exchange}:{symbol} "
            f"(also tried {other})"
        )