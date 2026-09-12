from datetime import datetime, time

from backend.collectors.market.instrument_resolver import (
    InstrumentResolver,
)
from backend.collectors.market.collector import (
    MarketDataCollector,
)
from backend.collectors.market.zerodha_instruments import (
    ZerodhaInstrumentSource,
)
from backend.collectors.market.zerodha_source import (
    ZerodhaDataSource,
)


class ListingDayCollector:
    """Collect and store 1-minute candles for an IPO listing day."""

    def __init__(
        self,
        instrument_resolver=None,
        market_collector=None,
    ):
        self.instrument_resolver = (
            instrument_resolver
            or InstrumentResolver(
                source=ZerodhaInstrumentSource(),
                provider="zerodha",
            )
        )

        self.market_collector = (
            market_collector
            or MarketDataCollector(
                ZerodhaDataSource()
            )
        )

    def collect(
        self,
        symbol: str,
        listing_date,
        company_name: str = "",
    ) -> dict:
        """Resolve listing instrument and collect NSE 1-minute candles."""

        instrument = self.instrument_resolver.resolve(
            symbol=symbol,
            company_name=company_name,
            valid_from=listing_date,
        )

        if instrument is None:
            return {
                "status": "NOT_AVAILABLE",
                "symbol": symbol.upper(),
                "listing_date": listing_date.isoformat(),
                "reason": (
                    f"{self.instrument_resolver.provider} "
                    "instrument is not available yet."
                ),
                "instrument": None,
            }

        start = datetime.combine(
            listing_date,
            time(9, 15),
        )

        end = datetime.combine(
            listing_date,
            time(15, 30),
        )

        result = self.market_collector.collect(
            symbol=instrument.provider_instrument_id,
            start=start,
            end=end,
            interval="1m",
        )

        return {
            "status": "COLLECTED",
            "symbol": instrument.symbol,
            "listing_date": listing_date.isoformat(),
            "instrument": instrument,
            "collection": result,
        }