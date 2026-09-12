from backend.collectors.market_data.angel_one_candle_source import (
    AngelOneCandleSource,
)
from backend.collectors.market_data.angel_one_instrument_resolver import (
    AngelOneInstrumentResolver,
)
from backend.storage.ipo_candle_repository import (
    IPOCandleRepository,
)
from backend.storage.ipo_repository import IPORepository


class IPOHistoricalDataCollector:
    """
    Collect and persist listing-day historical candles for IPOs.
    """

    def __init__(
        self,
        candle_source=None,
        candle_repository=None,
        ipo_repository=None,
        instrument_resolver=None,
    ):
        self.candle_source = (
            candle_source
            or AngelOneCandleSource()
        )

        self.candle_repository = (
            candle_repository
            or IPOCandleRepository()
        )

        self.ipo_repository = (
            ipo_repository
            or IPORepository()
        )

        self.instrument_resolver = (
            instrument_resolver
            or AngelOneInstrumentResolver()
        )

    def collect_one(
        self,
        ipo: dict,
        interval: str = "ONE_MINUTE",
    ) -> dict:
        company_name = ipo["company_name"]
        symbol = ipo["symbol"]
        listing_date = ipo["listing_date"]

        if not symbol:
            return {
                "status": "NOT_EVALUABLE",
                "company_name": company_name,
                "reason": "Trading symbol is unavailable.",
            }

        ipo_id = ipo["id"]

        instrument = self.instrument_resolver.find(
            symbol=symbol,
            exchange="NSE",
        )

        provider_instrument_id = instrument["token"]
        resolved_symbol = instrument["symbol"]

        candles = self.candle_source.fetch(
            symbol=symbol,
            listing_date=listing_date,
            interval=interval,
        )

        inserted = 0
        skipped = 0

        for candle in candles:
            saved = self.candle_repository.save_candle(
                symbol=provider_instrument_id,
                timestamp=candle["timestamp"],
                open_price=candle["open_price"],
                high_price=candle["high_price"],
                low_price=candle["low_price"],
                close_price=candle["close_price"],
                volume=candle.get("volume"),
                interval="1m",
                source="angel_one",
                ipo_id=ipo_id,
                provider_instrument_id=provider_instrument_id,
            )

            if saved:
                inserted += 1
            else:
                skipped += 1

        return {
            "status": "COLLECTED",
            "ipo_id": ipo_id,
            "company_name": company_name,
            "symbol": resolved_symbol,
            "provider_instrument_id": provider_instrument_id,
            "listing_date": listing_date,
            "collection": {
                "fetched": len(candles),
                "inserted": inserted,
                "skipped": skipped,
            },
        }