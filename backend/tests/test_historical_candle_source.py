from backend.tests.test_candle_source import (
    TestHistoricalCandleSource,
)


def main():
    source = TestHistoricalCandleSource()

    candles = source.fetch(
        symbol="TESTIPO",
        listing_date="2026-08-26",
        interval="1m",
    )

    print("=" * 60)
    print("HISTORICAL CANDLE SOURCE TEST")
    print("=" * 60)

    print("Candles:", len(candles))

    for item in candles:
        print(item)

    assert len(candles) == 2
    assert candles[0]["timestamp"] < candles[1]["timestamp"]
    assert candles[0]["open_price"] == 100.0
    assert candles[1]["close_price"] == 101.5

    print()
    print("HISTORICAL CANDLE SOURCE TEST PASSED")


if __name__ == "__main__":
    main()