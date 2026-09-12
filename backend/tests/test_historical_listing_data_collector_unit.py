from datetime import date

from backend.collectors.listing.listing_day_collector import (
    ListingDayCollector,
)
from backend.collectors.market.collector import (
    MarketDataCollector,
)
from backend.collectors.market.instrument_resolver import (
    InstrumentResolver,
)
from backend.services.historical_listing_data_collector import (
    HistoricalListingDataCollector,
)


class FakeInstrumentSource:

    def find_symbol(self, symbol):
        return {
            "exchange": "NSE",
            "segment": "NSE",
            "instrument_token": 12345,
            "tradingsymbol": symbol,
            "name": "TEST COMPANY",
            "isin": None,
        }


class FakeMarketSource:

    def get_candles(
        self,
        symbol,
        start,
        end,
        interval="1m",
    ):
        return [
            {
                "timestamp": start,
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 1000,
                "source": "test",
            }
        ]


def test_historical_listing_collector_with_fake_data():

    resolver = InstrumentResolver(
        source=FakeInstrumentSource(),
        provider="zerodha",
    )

    collector = HistoricalListingDataCollector(
        listing_day_collector=ListingDayCollector(
            instrument_resolver=resolver,
            market_collector=MarketDataCollector(
                FakeMarketSource()
            ),
        )
    )

    ipo = {
        "id": 1,
        "company_name": "TEST COMPANY",
        "symbol": "TEST",
        "listing_date": date.today().isoformat(),
    }

    result = collector.collect_one(
        ipo,
        skip_existing=False,
    )

    assert result["status"] == "COLLECTED"
    assert result["collection"]["fetched"] == 1
    assert result["collection"]["errors"] == []