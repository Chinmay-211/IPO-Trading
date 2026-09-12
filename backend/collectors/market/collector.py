from datetime import datetime

from backend.models.candle import Candle
from backend.storage.candle_repository import CandleRepository


class MarketDataCollector:
    """Fetch, normalize, and store market candles."""

    def __init__(self, source):
        self.source = source
        self.repository = CandleRepository()

    def collect(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> dict:

        raw_candles = self.source.get_candles(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
        )

        inserted = 0
        skipped = 0
        errors = []

        for raw in raw_candles:
            try:
                candle = Candle(
                    symbol=symbol,
                    timestamp=raw["timestamp"],
                    open_price=float(raw["open"]),
                    high_price=float(raw["high"]),
                    low_price=float(raw["low"]),
                    close_price=float(raw["close"]),
                    volume=(
                        int(raw["volume"])
                        if raw.get("volume") is not None
                        else None
                    ),
                    interval=interval,
                    source=raw.get("source", "unknown"),
                )

                if self.repository.add(candle):
                    inserted += 1
                else:
                    skipped += 1

            except Exception as exc:
                errors.append({
                    "record": raw,
                    "error": str(exc),
                })

        return {
            "symbol": symbol,
            "interval": interval,
            "fetched": len(raw_candles),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }