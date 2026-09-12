from datetime import datetime

from backend.collectors.live.candle_builder import (
    OneMinuteCandleBuilder,
)


def test_first_tick_starts_candle():
    builder = OneMinuteCandleBuilder()

    result = builder.update(
        symbol="HORIZONIND",
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
        price=100.0,
        volume=10,
    )

    assert result is None


def test_ticks_build_one_minute_candle():
    builder = OneMinuteCandleBuilder()

    builder.update(
        symbol="HORIZONIND",
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
        price=100.0,
        volume=10,
    )

    builder.update(
        symbol="HORIZONIND",
        timestamp=datetime(2026, 8, 31, 9, 15, 20),
        price=105.0,
        volume=20,
    )

    builder.update(
        symbol="HORIZONIND",
        timestamp=datetime(2026, 8, 31, 9, 15, 50),
        price=98.0,
        volume=30,
    )

    completed = builder.update(
        symbol="HORIZONIND",
        timestamp=datetime(2026, 8, 31, 9, 16, 1),
        price=101.0,
        volume=15,
    )

    assert completed is not None

    assert completed.symbol == "HORIZONIND"
    assert completed.timestamp == datetime(
        2026, 8, 31, 9, 15
    )

    assert completed.open == 100.0
    assert completed.high == 105.0
    assert completed.low == 98.0
    assert completed.close == 98.0
    assert completed.volume == 60


def test_symbols_are_tracked_independently():
    builder = OneMinuteCandleBuilder()

    builder.update(
        symbol="HORIZONIND",
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
        price=100.0,
        volume=10,
    )

    builder.update(
        symbol="LALITHAA",
        timestamp=datetime(2026, 8, 31, 9, 15, 20),
        price=200.0,
        volume=20,
    )

    completed = builder.update(
        symbol="HORIZONIND",
        timestamp=datetime(2026, 8, 31, 9, 16, 1),
        price=101.0,
        volume=5,
    )

    assert completed is not None
    assert completed.symbol == "HORIZONIND"
    assert completed.close == 100.0


def test_flush_returns_open_candle():
    builder = OneMinuteCandleBuilder()

    builder.update(
        symbol="LALITHAA",
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
        price=200.0,
        volume=10,
    )

    candle = builder.flush("LALITHAA")

    assert candle is not None
    assert candle.symbol == "LALITHAA"
    assert candle.open == 200.0
    assert candle.high == 200.0
    assert candle.low == 200.0
    assert candle.close == 200.0
    assert candle.volume == 10

    assert builder.flush("LALITHAA") is None