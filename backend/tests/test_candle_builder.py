from datetime import datetime

import pytest

from backend.collectors.market.candle_builder import (
    OneMinuteCandleBuilder,
)


def test_first_tick_starts_candle():
    builder = OneMinuteCandleBuilder()

    result = builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 10),
        "ltp": 100.0,
        "volume": 10,
    })

    assert result is None

    candle = builder.current_candle

    assert candle is not None
    assert candle["symbol"] == "TEST-EQ"
    assert candle["timestamp"] == datetime(
        2026, 8, 31, 9, 15
    )
    assert candle["open"] == 100.0
    assert candle["high"] == 100.0
    assert candle["low"] == 100.0
    assert candle["close"] == 100.0
    assert candle["volume"] == 10


def test_ticks_build_one_minute_candle():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 1),
        "ltp": 100.0,
        "volume": 10,
    })

    builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 20),
        "ltp": 105.0,
        "volume": 20,
    })

    builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 50),
        "ltp": 98.0,
        "volume": 30,
    })

    candle = builder.current_candle

    assert candle["open"] == 100.0
    assert candle["high"] == 105.0
    assert candle["low"] == 98.0
    assert candle["close"] == 98.0
    assert candle["volume"] == 60


def test_new_minute_closes_previous_candle():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 10),
        "ltp": 100.0,
        "volume": 10,
    })

    builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 50),
        "ltp": 105.0,
        "volume": 20,
    })

    completed = builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 16, 2),
        "ltp": 103.0,
        "volume": 5,
    })

    assert completed is not None
    assert completed["timestamp"] == datetime(
        2026, 8, 31, 9, 15
    )
    assert completed["open"] == 100.0
    assert completed["high"] == 105.0
    assert completed["low"] == 100.0
    assert completed["close"] == 105.0
    assert completed["volume"] == 30

    current = builder.current_candle

    assert current is not None
    assert current["timestamp"] == datetime(
        2026, 8, 31, 9, 16
    )
    assert current["open"] == 103.0
    assert current["close"] == 103.0


def test_out_of_order_tick_is_ignored():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 30),
        "ltp": 100.0,
        "volume": 10,
    })

    result = builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 14, 30),
        "ltp": 50.0,
        "volume": 100,
    })

    assert result is None

    candle = builder.current_candle

    assert candle["open"] == 100.0
    assert candle["close"] == 100.0
    assert candle["volume"] == 10


def test_flush_closes_current_candle():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "TEST-EQ",
        "timestamp": datetime(2026, 8, 31, 9, 15, 10),
        "ltp": 100.0,
        "volume": 10,
    })

    candle = builder.flush()

    assert candle is not None
    assert candle["close"] == 100.0
    assert builder.current_candle is None


def test_invalid_tick_is_rejected():
    builder = OneMinuteCandleBuilder()

    with pytest.raises(ValueError):
        builder.update({
            "symbol": "TEST-EQ",
        })