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


def test_angel_one_market_data_source():
    source = AngelOneDataSource()

    candles = source.get_candles(
        symbol="2885",
        start=datetime(2026, 8, 27, 9, 15),
        end=datetime(2026, 8, 27, 9, 20),
        interval="1m",
    )

    print(f"\nCandles received: {len(candles)}")

    for candle in candles[:5]:
        print(candle)

    assert isinstance(candles, list)

    assert len(candles) > 0

    candle = candles[0]

    assert "timestamp" in candle
    assert "open" in candle
    assert "high" in candle
    assert "low" in candle
    assert "close" in candle
    assert "volume" in candle
    assert candle["source"] == "angel_one"


if __name__ == "__main__":
    test_angel_one_market_data_source()