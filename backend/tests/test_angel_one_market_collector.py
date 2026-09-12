import os
from datetime import datetime

import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

from backend.collectors.market.angel_one_source import (
    AngelOneDataSource,
)
from backend.collectors.market.collector import (
    MarketDataCollector,
)


def test_angel_one_market_data_collector():
    collector = MarketDataCollector(
        AngelOneDataSource()
    )

    result = collector.collect(
        symbol="2885",
        start=datetime(2026, 8, 27, 9, 15),
        end=datetime(2026, 8, 27, 9, 20),
        interval="1m",
    )

    print("\nCollection result:")
    print(result)

    assert result["fetched"] > 0
    assert result["inserted"] + result["skipped"] > 0
    assert result["errors"] == []


if __name__ == "__main__":
    test_angel_one_market_data_collector()