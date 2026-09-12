from backend.services.ipo_historical_backtest_runner import (
    IPOHistoricalBacktestRunner,
)


def test_ipo_historical_backtest_runner():
    runner = IPOHistoricalBacktestRunner()

    print("=" * 60)
    print("IPO HISTORICAL BACKTEST RUNNER TEST")
    print("=" * 60)

    from backend.storage.database import get_connection
    _conn = get_connection()
    try:
        _conn.execute(
            """
            INSERT OR REPLACE INTO ipo_discoveries (id, chittorgarh_ipo_id, company_name, ipo_type, listing_date, detail_url, status, discovered_at, updated_at)
            VALUES (19, 2574, 'Lohia Corp Ltd.', 'MAINBOARD', '2026-07-30', 'https://www.chittorgarh.com/ipo/lohia-corp-ipo/2574/', 'FAILED', '2026-08-25T20:57:34', '2026-08-26T15:47:42')
            """
        )
        _conn.execute(
            """
            INSERT OR REPLACE INTO ipo_discoveries (id, chittorgarh_ipo_id, company_name, ipo_type, listing_date, detail_url, status, discovered_at, updated_at)
            VALUES (17, 2826, 'Horizon Industrial Parks Ltd.', 'MAINBOARD', '2026-08-24', 'https://www.chittorgarh.com/ipo/horizon-industrial-parks-ipo/2826/', 'FAILED', '2026-08-25T20:57:34', '2026-08-26T15:47:42')
            """
        )
        _conn.execute(
            """
            INSERT OR REPLACE INTO ipos (id, symbol, company_name, listing_date, issue_price, source, collected_at)
            VALUES (201, 'HORIZONIND', 'Horizon Industrial Parks Ltd.', '2026-08-24', 500.0, 'test', '2026-08-24T10:00:00')
            """
        )
        _conn.commit()
    finally:
        _conn.close()

    # ---------------------------------------------------------
    # TEST 1: PASS screening but symbol is unavailable.
    # Runner must refuse to fabricate a trade.
    # ---------------------------------------------------------
    screening = {
        "company_name": "Lohia Corp Ltd.",
        "chittorgarh_ipo_id": 2574,
        "strategy_result": "PASS",
        "symbol": None,
    }

    result = runner.run_one(
        screening=screening,
    )

    print(result)

    assert result["outcome"] == "NOT_EVALUABLE"
    assert (
        result["reason"]
        == "Trading symbol is unavailable."
    )

    # ---------------------------------------------------------
    # TEST 2: Failed screening must never reach
    # the historical candle strategy.
    # ---------------------------------------------------------
    failed_screening = {
        "company_name": "Test Failed IPO",
        "chittorgarh_ipo_id": 2574,
        "strategy_result": "FAIL",
        "symbol": "TESTIPO",
    }

    failed_result = runner.run_one(
        screening=failed_screening,
    )

    print(failed_result)

    assert failed_result["outcome"] == "NO_TRADE"

    # ---------------------------------------------------------
    # TEST 3: Real historical IPO.
    #
    # Chittorgarh ID = 2826
    # Internal IPO ID = 201
    # Symbol = HORIZONIND
    # Listing date = 2026-08-24
    # Expected candles = 330
    #
    # This verifies:
    #
    # screening
    #     -> discovery
    #     -> internal ipo_id
    #     -> persisted candles
    #     -> listing-day strategy
    #     -> trade result
    # ---------------------------------------------------------
    horizon_screening = {
        "company_name": "Horizon Industrial Parks Ltd.",
        "chittorgarh_ipo_id": 2826,
        "strategy_result": "PASS",
        "symbol": "HORIZONIND",
    }

    from backend.storage.database import get_connection
    _conn = get_connection()
    try:
        _conn.execute(
            """
            INSERT OR REPLACE INTO ipos (id, symbol, company_name, listing_date, issue_price, source, collected_at)
            VALUES (201, 'HORIZONIND', 'Horizon Industrial Parks Ltd.', '2026-08-24', 500.0, 'test', '2026-08-24T10:00:00')
            """
        )
        _conn.commit()
    finally:
        _conn.close()

    horizon_result = runner.run_one(
        screening=horizon_screening,
    )

    print(horizon_result)

    assert horizon_result["outcome"] in {
        "TARGET",
        "STOP_LOSS",
        "NO_TRADE",
    }

    assert horizon_result["symbol"] == "HORIZONIND"
    assert horizon_result["listing_date"] == "2026-08-24"

    print("REAL HISTORICAL IPO TEST PASSED")


def test_calculate_summary_metrics_empty():
    metrics = IPOHistoricalBacktestRunner.calculate_summary_metrics([])
    assert metrics["total_ipos_screened"] == 0
    assert metrics["trades_executed"] == 0
    assert metrics["win_rate_pct"] == 0.0
    assert metrics["profit_factor"] == 0.0


def test_calculate_summary_metrics_with_trades():
    mock_results = [
        {
            "symbol": "WINNER",
            "outcome": "TARGET",
            "entry_price": 100.0,
            "exit_price": 110.0,  # +10%
        },
        {
            "symbol": "LOSER",
            "outcome": "STOP_LOSS",
            "entry_price": 100.0,
            "exit_price": 95.0,  # -5%
        },
        {
            "symbol": "NOTRADER",
            "outcome": "NO_TRADE",
            "entry_price": None,
            "exit_price": None,
        },
        {
            "symbol": "INVALID",
            "outcome": "NOT_EVALUABLE",
            "entry_price": None,
            "exit_price": None,
        },
    ]

    # Without slippage
    metrics = IPOHistoricalBacktestRunner.calculate_summary_metrics(mock_results, slippage_pct=0.0)
    assert metrics["total_ipos_screened"] == 4
    assert metrics["trades_executed"] == 2
    assert metrics["no_trades"] == 1
    assert metrics["not_evaluable"] == 1
    assert metrics["target_hits"] == 1
    assert metrics["stop_loss_hits"] == 1
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["gross_profit"] == 10.0
    assert metrics["gross_loss"] == 5.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["avg_win_pnl_pct"] == 10.0
    assert metrics["avg_loss_pnl_pct"] == -5.0
    assert metrics["risk_reward_ratio"] == 2.0
    assert metrics["net_pnl"] == 5.0

    # With 1% slippage
    # Winner: eff entry 101, eff exit 108.9 -> pnl = 7.9
    # Loser: eff entry 101, eff exit 94.05 -> pnl = -6.95
    s_metrics = IPOHistoricalBacktestRunner.calculate_summary_metrics(mock_results, slippage_pct=0.01)
    assert s_metrics["slippage_pct"] == 0.01
    assert s_metrics["gross_profit"] == 7.9
    assert s_metrics["gross_loss"] == 6.95
    assert s_metrics["net_pnl"] == 0.95


def test_run_backtest_with_summary():
    runner = IPOHistoricalBacktestRunner()
    screening = [
        {
            "company_name": "Horizon Industrial Parks Ltd.",
            "chittorgarh_ipo_id": 2826,
            "strategy_result": "PASS",
            "symbol": "HORIZONIND",
        }
    ]
    report = runner.run_backtest_with_summary(screening, interval="1m", slippage_pct=0.002)
    assert "summary" in report
    assert "results" in report
    assert report["summary"]["total_ipos_screened"] == 1
    assert report["summary"]["slippage_pct"] == 0.002