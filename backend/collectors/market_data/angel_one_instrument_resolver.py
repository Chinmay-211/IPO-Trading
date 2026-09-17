from datetime import datetime, timedelta, timezone
import json
import os
import time

import requests


INSTRUMENT_URL = (
    "https://margincalculator.angelone.in/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)

# Indian Standard Time (UTC+05:30) for daily listing market schedule
IST = timezone(timedelta(hours=5, minutes=30))


class AngelOneInstrumentResolver:
    """Resolves NSE/BSE symbols to Angel One instrument tokens."""

    def __init__(
        self,
        cache_path: str | None = None,
        cache_ttl_hours: int = 24,
    ):
        self._instruments = None
        self._loaded_at = 0
        self._last_remote_fetch = 0
        self._is_stale_fallback = False
        self._last_fallback_attempt = 0
        self.cache_path = cache_path or os.path.join(
            "data", "cache", "angel_one_instruments.json"
        )
        self.cache_ttl_seconds = cache_ttl_hours * 3600

    def _is_cache_valid(self) -> bool:
        """Check if local cache file is fresh.

        Cache is stale if:
        1. File does not exist.
        2. Age exceeds cache_ttl_seconds (default: 24h).
        3. Past 08:30 AM IST today, but cache was created before 08:30 AM IST today
           (Angel One adds newly listing IPO tokens between 08:00-09:00 AM IST).
        """
        if not os.path.exists(self.cache_path):
            return False

        mtime = os.path.getmtime(self.cache_path)
        now = time.time()
        if (now - mtime) >= self.cache_ttl_seconds:
            return False

        # ponytail: daily 08:30 AM IST market cutoff check for new listing day tokens.
        # Ceiling: assumes standard Indian market pre-open schedule.
        try:
            now_dt = datetime.now(IST)
            mtime_dt = datetime.fromtimestamp(mtime, tz=IST)
            cutoff_today = now_dt.replace(hour=8, minute=30, second=0, microsecond=0)
            if now_dt >= cutoff_today and mtime_dt < cutoff_today:
                return False
        except Exception:
            pass

        return True

    def _needs_refresh(self) -> bool:
        """Check if memory instruments need to be reloaded or refreshed."""
        if self._instruments is None:
            return True

        now = time.time()
        # 1. Auto-healing: If operating on a stale fallback (because Angel One was down earlier),
        # retry remote download every 60s once the server is back online.
        if getattr(self, "_is_stale_fallback", False):
            return (now - getattr(self, "_last_fallback_attempt", 0)) > 60

        # 2. Daily 08:30 AM IST morning invalidation for in-memory instruments:
        # If in-memory instruments were loaded before today's 08:30 AM IST cutoff,
        # but it is now past 08:30 AM IST, mark them stale to fetch today's IPO tokens.
        try:
            now_dt = datetime.now(IST)
            loaded_dt = datetime.fromtimestamp(getattr(self, "_loaded_at", 0), tz=IST)
            cutoff_today = now_dt.replace(hour=8, minute=30, second=0, microsecond=0)
            if now_dt >= cutoff_today and loaded_dt < cutoff_today:
                return True
        except Exception:
            pass

        return False

    def _load_instruments(self, force_refresh: bool = False):
        if not force_refresh and not self._needs_refresh():
            return

        # 1. Try valid cache from disk (only if not forcing refresh and not recovering from stale fallback)
        if not force_refresh and not getattr(self, "_is_stale_fallback", False) and self._is_cache_valid():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._instruments = data
                        self._loaded_at = time.time()
                        self._is_stale_fallback = False
                        return
            except Exception:
                pass

        # 2. Attempt remote download
        try:
            response = requests.get(
                INSTRUMENT_URL,
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            self._instruments = data
            self._loaded_at = time.time()
            self._last_remote_fetch = time.time()
            self._is_stale_fallback = False

            # Save fresh cache to disk
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return
        except Exception:
            # 3. Fallback to existing stale cache if network/server fails
            self._last_fallback_attempt = time.time()
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self._instruments = data
                            self._loaded_at = time.time()
                            self._is_stale_fallback = True
                            return
                except Exception:
                    pass
            if self._instruments is not None:
                self._is_stale_fallback = True
                return
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

        # ponytail: on-miss live refresh. If symbol not found in current cache, retry once
        # with a fresh remote pull (debounced by 300s to avoid hammering Angel One API).
        # Ceiling: push notification / webhook on new listing scrips.
        now = time.time()
        if (now - getattr(self, "_last_remote_fetch", 0)) > 300:
            try:
                self._load_instruments(force_refresh=True)
                result = _search(exchange) or _search(other)
                if result is not None:
                    return result
            except Exception:
                pass

        raise ValueError(
            f"Instrument not found: {exchange}:{symbol} "
            f"(also tried {other})"
        )