from datetime import datetime

from backend.collectors.market.one_minute_candle_builder import (
    OneMinuteCandleBuilder,
)


def test_first_tick_starts_candle():
    builder = OneMinuteCandleBuilder()

    result = builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 15, 10
        ),
        "price": 100.0,
        "volume": 100,
    })

    assert result is None


def test_ticks_same_minute_update_candle():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 15, 10
        ),
        "price": 100.0,
        "volume": 100,
    })

    builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 15, 30
        ),
        "price": 105.0,
        "volume": 150,
    })

    result = builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 16, 5
        ),
        "price": 103.0,
        "volume": 200,
    })

    assert result is not None
    assert result["symbol"] == "ARCIIL-SM"
    assert result["timestamp"] == datetime(
        2026, 8, 31, 9, 15
    )
    assert result["open"] == 100.0
    assert result["high"] == 105.0
    assert result["low"] == 100.0
    assert result["close"] == 105.0
    assert result["volume"] == 150


def test_new_minute_starts_new_candle():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 15, 10
        ),
        "price": 100.0,
    })

    builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 16, 5
        ),
        "price": 102.0,
    })

    result = builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 17, 5
        ),
        "price": 104.0,
    })

    assert result is not None

    assert result["timestamp"] == datetime(
        2026, 8, 31, 9, 16
    )

    assert result["open"] == 102.0
    assert result["high"] == 102.0
    assert result["low"] == 102.0
    assert result["close"] == 102.0


def test_multiple_symbols_are_independent():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 15, 10
        ),
        "price": 100.0,
    })

    builder.update({
        "symbol": "HORIZONIND-EQ",
        "timestamp": datetime(
            2026, 8, 31, 9, 15, 20
        ),
        "price": 200.0,
    })

    result = builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 16, 1
        ),
        "price": 101.0,
    })

    assert result is not None
    assert result["symbol"] == "ARCIIL-SM"


def test_flush_returns_open_candle():
    builder = OneMinuteCandleBuilder()

    builder.update({
        "symbol": "ARCIIL-SM",
        "timestamp": datetime(
            2026, 8, 31, 9, 15, 10
        ),
        "price": 100.0,
    })

    result = builder.flush("ARCIIL-SM")

    assert len(result) == 1
    assert result[0]["symbol"] == "ARCIIL-SM"
    assert result[0]["open"] == 100.0
    assert result[0]["close"] == 100.0