from datetime import datetime

from backend.services.ipo_live_market_data_service import (
    IPOLiveMarketDataService,
)


def test_first_tick_starts_candle():
    service = IPOLiveMarketDataService()

    result = service.process_tick(
        symbol="TESTIPO",
        price=100,
        volume=10,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    assert result is None


def test_same_minute_updates_candle():
    service = IPOLiveMarketDataService()

    service.process_tick(
        symbol="TESTIPO",
        price=100,
        volume=10,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    service.process_tick(
        symbol="TESTIPO",
        price=105,
        volume=20,
        timestamp=datetime(2026, 8, 31, 9, 15, 30),
    )

    service.process_tick(
        symbol="TESTIPO",
        price=98,
        volume=30,
        timestamp=datetime(2026, 8, 31, 9, 15, 50),
    )

    candle = service.flush()

    assert candle["symbol"] == "TESTIPO"
    assert candle["timestamp"] == datetime(
        2026, 8, 31, 9, 15
    )

    assert candle["open"] == 100
    assert candle["high"] == 105
    assert candle["low"] == 98
    assert candle["close"] == 98
    assert candle["volume"] == 60


def test_new_minute_finalizes_previous_candle():
    service = IPOLiveMarketDataService()

    service.process_tick(
        symbol="TESTIPO",
        price=100,
        volume=10,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    completed = service.process_tick(
        symbol="TESTIPO",
        price=103,
        volume=20,
        timestamp=datetime(2026, 8, 31, 9, 16, 5),
    )

    assert completed is not None

    assert completed["timestamp"] == datetime(
        2026, 8, 31, 9, 15
    )

    assert completed["open"] == 100
    assert completed["high"] == 100
    assert completed["low"] == 100
    assert completed["close"] == 100
    assert completed["volume"] == 10


def test_new_minute_starts_new_candle():
    service = IPOLiveMarketDataService()

    service.process_tick(
        symbol="TESTIPO",
        price=100,
        volume=10,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    service.process_tick(
        symbol="TESTIPO",
        price=103,
        volume=20,
        timestamp=datetime(2026, 8, 31, 9, 16, 5),
    )

    candle = service.flush()

    assert candle["timestamp"] == datetime(
        2026, 8, 31, 9, 16
    )

    assert candle["open"] == 103
    assert candle["high"] == 103
    assert candle["low"] == 103
    assert candle["close"] == 103
    assert candle["volume"] == 20


def test_callback_receives_completed_candle():
    received = []

    def on_candle(candle):
        received.append(candle)

    service = IPOLiveMarketDataService(
        on_candle=on_candle
    )

    service.process_tick(
        symbol="TESTIPO",
        price=100,
        volume=10,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    service.process_tick(
        symbol="TESTIPO",
        price=105,
        volume=20,
        timestamp=datetime(2026, 8, 31, 9, 16, 5),
    )

    assert len(received) == 1
    assert received[0]["symbol"] == "TESTIPO"
    assert received[0]["open"] == 100
    assert received[0]["close"] == 100


def test_flush_returns_current_candle_and_resets():
    service = IPOLiveMarketDataService()

    service.process_tick(
        symbol="TESTIPO",
        price=100,
        volume=10,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    candle = service.flush()

    assert candle is not None
    assert candle["close"] == 100

    assert service.flush() is None


def test_reset_discards_current_candle():
    service = IPOLiveMarketDataService()

    service.process_tick(
        symbol="TESTIPO",
        price=100,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    service.reset()

    assert service.flush() is None


def test_invalid_symbol_is_rejected():
    service = IPOLiveMarketDataService()

    try:
        service.process_tick(
            symbol="",
            price=100,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "symbol is required."


def test_invalid_price_is_rejected():
    service = IPOLiveMarketDataService()

    try:
        service.process_tick(
            symbol="TESTIPO",
            price=0,
        )
        assert False
    except ValueError as exc:
        assert str(exc) == "price must be greater than zero."


def test_symbol_is_normalized():
    service = IPOLiveMarketDataService()

    service.process_tick(
        symbol=" testipo ",
        price=100,
        timestamp=datetime(2026, 8, 31, 9, 15, 10),
    )

    candle = service.flush()

    assert candle["symbol"] == "TESTIPO"