import os

import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

from backend.collectors.listing.listing_day_collector import (
    ListingDayCollector,
)
from backend.collectors.market.angel_one_instruments import (
    AngelOneInstrumentSource,
)
from backend.collectors.market.angel_one_source import (
    AngelOneDataSource,
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


def test_historical_listing_data_collector_one_ipo():

    collector = HistoricalListingDataCollector(
        listing_day_collector=ListingDayCollector(
            instrument_resolver=InstrumentResolver(
                source=AngelOneInstrumentSource(),
                provider="angel_one",
            ),
            market_collector=MarketDataCollector(
                AngelOneDataSource()
            ),
        )
    )

    ipo = {
        "id": 192,
        "company_name": (
            "ARC Insulation & Insulators Limited"
        ),
        "symbol": "ARCIIL",
        "listing_date": "2025-08-29",
    }

    result = collector.collect_one(ipo)

    print("\nHistorical IPO collection:")
    print(result)

    assert result["status"] in {
        "COLLECTED",
        "NOT_AVAILABLE",
    }

    if result["status"] == "COLLECTED":
        assert result["collection"]["fetched"] >= 0