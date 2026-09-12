from backend.strategy.ipo_listing_day_strategy import (
    IPOListingDayStrategy,
)


def candle(
    timestamp,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
):
    return {
        "timestamp": timestamp,
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "close_price": close_price,
        "volume": volume,
    }


def build_base_candles():
    return [
        candle(
            "2026-08-26 09:15:00",
            100.0,
            101.0,
            99.5,
            100.0,
            1000,
        ),
        candle(
            "2026-08-26 09:16:00",
            100.0,
            100.5,
            99.0,
            99.5,
            1000,
        ),
        candle(
            "2026-08-26 09:17:00",
            99.5,
            100.0,
            98.5,
            99.0,
            1000,
        ),
        candle(
            "2026-08-26 09:18:00",
            99.0,
            99.5,
            98.0,
            98.5,
            1000,
        ),
        candle(
            "2026-08-26 09:19:00",
            98.5,
            99.0,
            98.0,
            98.5,
            1000,
        ),
    ]


def test_target_trade():
    strategy = IPOListingDayStrategy()

    candles = build_base_candles()

    # Establish the required 2% dip.
    candles.append(
        candle(
            "2026-08-26 09:20:00",
            98.5,
            99.0,
            98.0,
            98.2,
            1000,
        )
    )

    # Recovery + volume confirmation.
    # Close > listing opening price.
    # Volume = 2000 vs previous 5-candle average = 1000.
    candles.append(
        candle(
            "2026-08-26 09:21:00",
            98.2,
            100.8,
            98.2,
            100.2,
            2000,
        )
    )

    # BUY happens at this candle's OPEN.
    candles.append(
        candle(
            "2026-08-26 09:22:00",
            100.5,
            101.0,
            100.2,
            100.8,
            1000,
        )
    )

    # Entry = 100.5
    # Dip low = 98.0
    # Stop = 98.0
    # Risk = 2.5
    # Target = 105.5
    candles.append(
        candle(
            "2026-08-26 09:23:00",
            100.8,
            106.0,
            100.5,
            105.5,
            2000,
        )
    )

    result = strategy.run(candles)

    print(result)

    assert result.outcome == "TARGET"
    assert result.entry_price == 100.5
    assert result.stop_loss_price == 98.0
    assert result.target_price == 105.5
    assert result.exit_price == 105.5
    assert result.profit_loss == 5.0
    assert result.profit_loss_percent > 0


def test_no_trade_without_dip():
    strategy = IPOListingDayStrategy()

    candles = [
        candle(
            "2026-08-26 09:15:00",
            100.0,
            101.0,
            99.5,
            100.0,
            1000,
        ),
        candle(
            "2026-08-26 09:16:00",
            100.0,
            101.0,
            99.5,
            100.5,
            1000,
        ),
        candle(
            "2026-08-26 09:17:00",
            100.5,
            102.0,
            100.0,
            101.5,
            1000,
        ),
        candle(
            "2026-08-26 09:18:00",
            101.5,
            103.0,
            101.0,
            102.5,
            1000,
        ),
        candle(
            "2026-08-26 09:19:00",
            102.5,
            104.0,
            102.0,
            103.5,
            1000,
        ),
        candle(
            "2026-08-26 09:20:00",
            103.5,
            105.0,
            103.0,
            104.0,
            2000,
        ),
    ]

    result = strategy.run(candles)

    assert result.outcome == "NO_TRADE"


def test_failed_volume_confirmation():
    strategy = IPOListingDayStrategy()

    candles = build_base_candles()

    # Required dip.
    candles.append(
        candle(
            "2026-08-26 09:20:00",
            98.5,
            99.0,
            98.0,
            98.5,
            1000,
        )
    )

    # Recovery occurs, but volume is only 1000.
    # Required volume = 1500.
    candles.append(
        candle(
            "2026-08-26 09:21:00",
            98.5,
            100.5,
            98.4,
            100.1,
            1000,
        )
    )

    result = strategy.run(candles)

    assert result.outcome == "NO_TRADE"


def test_same_candle_stop_and_target_uses_stop():
    strategy = IPOListingDayStrategy()

    candles = build_base_candles()

    # Required dip.
    candles.append(
        candle(
            "2026-08-26 09:20:00",
            98.5,
            99.0,
            98.0,
            98.5,
            1000,
        )
    )

    # Recovery + volume confirmation.
    candles.append(
        candle(
            "2026-08-26 09:21:00",
            98.5,
            100.5,
            98.4,
            100.1,
            2000,
        )
    )

    # BUY at 100.5.
    # Stop = 98.0.
    # Target = 105.5.
    # Both are touched in this candle.
    candles.append(
        candle(
            "2026-08-26 09:22:00",
            100.5,
            106.0,
            97.0,
            102.0,
            2000,
        )
    )

    result = strategy.run(candles)

    print(result)

    assert result.outcome == "STOP_LOSS"
    assert result.exit_price == 98.0


def test_failed_screening_means_no_trade():
    strategy = IPOListingDayStrategy()

    candles = build_base_candles()

    result = strategy.run(
        candles,
        strategy_result="FAIL",
    )

    assert result.outcome == "NO_TRADE"
    assert result.entry_price is None


def main():
    test_target_trade()
    print("TARGET TEST PASSED")

    test_no_trade_without_dip()
    print("NO-DIP TEST PASSED")

    test_failed_volume_confirmation()
    print("VOLUME TEST PASSED")

    test_same_candle_stop_and_target_uses_stop()
    print("SAME-CANDLE CONSERVATIVE TEST PASSED")

    test_failed_screening_means_no_trade()
    print("SCREENING-FAIL TEST PASSED")

    print()
    print("ALL LISTING-DAY STRATEGY TESTS PASSED")


if __name__ == "__main__":
    main()