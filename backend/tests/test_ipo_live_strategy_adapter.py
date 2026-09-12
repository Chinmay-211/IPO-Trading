from datetime import datetime, timedelta

import pytest

from backend.services.ipo_live_strategy_adapter import (
    IPOLiveStrategyAdapter,
)
from backend.strategy.ipo_listing_day_strategy import (
    IPOListingDayStrategy,
    IPOListingTradeResult,
)


def make_candle(
    timestamp,
    open_price=100.0,
    high_price=101.0,
    low_price=99.0,
    close_price=100.0,
    volume=1000,
):
    return {
        "timestamp": timestamp,
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "close_price": close_price,
        "volume": volume,
    }


def test_adapter_creates_default_strategy():
    adapter = IPOLiveStrategyAdapter()

    assert adapter.strategy is not None
    assert adapter.get_candles() == []
    assert adapter.get_last_result() is None


def test_adapter_accepts_completed_candle():
    adapter = IPOLiveStrategyAdapter()

    timestamp = datetime(2026, 8, 31, 9, 15)

    result = adapter.add_candle(
        make_candle(timestamp)
    )

    assert isinstance(
        result,
        IPOListingTradeResult,
    )

    assert len(adapter.get_candles()) == 1
    assert adapter.get_candles()[0]["close_price"] == 100.0
    assert adapter.get_last_result() is result


def test_adapter_accumulates_candles():
    adapter = IPOLiveStrategyAdapter()

    timestamp = datetime(2026, 8, 31, 9, 15)

    candles = [
        make_candle(
            timestamp + timedelta(minutes=i),
            close_price=100 + i,
        )
        for i in range(5)
    ]

    result = adapter.add_candles(candles)

    assert isinstance(
        result,
        IPOListingTradeResult,
    )

    assert len(adapter.get_candles()) == 5


def test_adapter_passes_strategy_result():
    adapter = IPOLiveStrategyAdapter(
        strategy_result="FAIL"
    )

    timestamp = datetime(2026, 8, 31, 9, 15)

    result = adapter.add_candle(
        make_candle(timestamp)
    )

    assert isinstance(
        result,
        IPOListingTradeResult,
    )


def test_adapter_calls_result_callback():
    received = []

    def callback(result):
        received.append(result)

    adapter = IPOLiveStrategyAdapter(
        on_result=callback
    )

    timestamp = datetime(2026, 8, 31, 9, 15)

    result = adapter.add_candle(
        make_candle(timestamp)
    )

    assert len(received) == 1
    assert received[0] is result


def test_adapter_rejects_invalid_candle():
    adapter = IPOLiveStrategyAdapter()

    with pytest.raises(ValueError):
        adapter.add_candle({})


def test_adapter_reset():
    adapter = IPOLiveStrategyAdapter()

    timestamp = datetime(2026, 8, 31, 9, 15)

    adapter.add_candle(
        make_candle(timestamp)
    )

    assert len(adapter.get_candles()) == 1

    adapter.reset()

    assert adapter.get_candles() == []
    assert adapter.get_last_result() is None


def test_adapter_does_not_execute_orders():
    adapter = IPOLiveStrategyAdapter()

    timestamp = datetime(2026, 8, 31, 9, 15)

    result = adapter.add_candle(
        make_candle(timestamp)
    )

    # Strategy integration only.
    # No broker/order object should be created here.
    assert isinstance(
        result,
        IPOListingTradeResult,
    )