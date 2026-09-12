from backend.storage.database import initialize_database
from backend.storage.ipo_candle_repository import IPOCandleRepository


def test_ipo_candle_repository():
    initialize_database()

    repository = IPOCandleRepository()

    symbol = "TESTIPO"
    listing_date = "2026-08-26"

    repository.save_candle(
        symbol=symbol,
        timestamp="2026-08-26 09:15:00",
        open_price=100.0,
        high_price=102.0,
        low_price=98.0,
        close_price=101.0,
        volume=10000,
        interval="1m",
        source="TEST",
    )

    repository.save_candle(
        symbol=symbol,
        timestamp="2026-08-26 09:16:00",
        open_price=101.0,
        high_price=103.0,
        low_price=99.0,
        close_price=102.0,
        volume=12000,
        interval="1m",
        source="TEST",
    )

    candles = repository.get_candles(
        symbol=symbol,
        listing_date=listing_date,
        interval="1m",
    )

    assert len(candles) == 2

    first = repository.get_first_candle(
        symbol=symbol,
        listing_date=listing_date,
    )

    last = repository.get_last_candle(
        symbol=symbol,
        listing_date=listing_date,
    )

    assert first is not None
    assert last is not None

    assert first["close_price"] == 101.0
    assert last["close_price"] == 102.0