import os
from datetime import date

import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

from backend.collectors.listing.listing_day_collector import (
    ListingDayCollector,
)
from backend.collectors.market.collector import (
    MarketDataCollector,
)
from backend.collectors.market.instrument_resolver import (
    InstrumentResolver,
)
from backend.collectors.market.angel_one_instruments import (
    AngelOneInstrumentSource,
)
from backend.collectors.market.angel_one_source import (
    AngelOneDataSource,
)


def test_listing_day_collector_with_angel_one():
    resolver = InstrumentResolver(
        source=AngelOneInstrumentSource(),
        provider="angel_one",
    )

    collector = ListingDayCollector(
        instrument_resolver=resolver,
        market_collector=MarketDataCollector(
            AngelOneDataSource()
        ),
    )

    result = collector.collect(
        symbol="RELIANCE-EQ",
        listing_date=date(2026, 8, 27),
        company_name="RELIANCE INDUSTRIES",
    )

    print("\nListing-day collection result:")
    print(result)

    assert result["status"] == "COLLECTED"

    assert result["instrument"] is not None
    assert (
        result["instrument"].provider
        == "angel_one"
    )

    assert (
        result["instrument"].provider_instrument_id
        == "2885"
    )

    collection = result["collection"]

    assert collection["fetched"] > 0
    assert collection["errors"] == []


if __name__ == "__main__":
    test_listing_day_collector_with_angel_one()