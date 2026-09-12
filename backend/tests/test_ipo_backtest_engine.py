from backend.strategy.ipo_backtest_engine import (
    IPOBacktestEngine,
)


def main():
    engine = IPOBacktestEngine()

    print("=" * 60)
    print("IPO BACKTEST ENGINE TEST")
    print("=" * 60)

    result = engine.run(
        ipo_id=2574,
        company_name="Lohia Corp Ltd.",
        strategy_result="PASS",
        listing_price=460.0,
        opening_price=461.0,
        high_price=508.65,
        low_price=461.0,
        closing_price=494.60,
        stop_loss_percent=5.0,
    )

    print("Result:")
    print(result)

    assert result.entry_price == 461.0
    assert result.stop_loss_price == 437.95
    assert result.exit_price == 494.60
    assert result.outcome == "CLOSED_AT_CLOSE"

    print()
    print("PASS-TRADE TEST PASSED")

    no_trade = engine.run(
        ipo_id=2574,
        company_name="Lohia Corp Ltd.",
        strategy_result="FAIL",
        listing_price=460.0,
        opening_price=461.0,
        high_price=508.65,
        low_price=461.0,
        closing_price=494.60,
    )

    assert no_trade.outcome == "NO_TRADE"
    assert no_trade.profit_loss is None

    print("NO-TRADE TEST PASSED")


if __name__ == "__main__":
    main()