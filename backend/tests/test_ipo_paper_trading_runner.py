from datetime import datetime

from backend.services.ipo_paper_trading_runner import (
    IPOPaperTradingRunner,
)


class FakeBacktestRunner:

    def __init__(self, result):
        self.result = result

    def run_one(
        self,
        screening,
        interval="1m",
    ):
        return self.result


def test_no_trade_does_not_execute():
    runner = IPOPaperTradingRunner(
        backtest_runner=FakeBacktestRunner(
            {
                "company_name": "Test IPO",
                "symbol": "TESTIPO",
                "outcome": "NO_TRADE",
                "reason": "No confirmation.",
            }
        )
    )

    result = runner.run_one(
        {
            "company_name": "Test IPO",
            "chittorgarh_ipo_id": 1,
            "strategy_result": "PASS",
            "symbol": "TESTIPO",
        }
    )

    assert result["status"] == "NO_TRADE"
    assert result["paper_trade"] is None
    assert runner.get_orders() == []


def test_not_evaluable_does_not_execute():
    runner = IPOPaperTradingRunner(
        backtest_runner=FakeBacktestRunner(
            {
                "company_name": "Test IPO",
                "symbol": "TESTIPO",
                "outcome": "NOT_EVALUABLE",
                "reason": "No candles.",
            }
        )
    )

    result = runner.run_one(
        {
            "company_name": "Test IPO",
            "chittorgarh_ipo_id": 1,
            "strategy_result": "PASS",
            "symbol": "TESTIPO",
        }
    )

    assert result["status"] == "NOT_EVALUABLE"
    assert runner.get_orders() == []


def test_target_trade_is_replayed():
    runner = IPOPaperTradingRunner(
        backtest_runner=FakeBacktestRunner(
            {
                "company_name": "Test IPO",
                "symbol": "TESTIPO",
                "outcome": "TARGET",
                "entry_time": datetime(
                    2026,
                    8,
                    24,
                    10,
                    0,
                ),
                "entry_price": 100.0,
                "exit_time": datetime(
                    2026,
                    8,
                    24,
                    11,
                    0,
                ),
                "exit_price": 110.0,
                "reason": "Target reached.",
            }
        )
    )

    result = runner.run_one(
        {
            "company_name": "Test IPO",
            "chittorgarh_ipo_id": 1,
            "strategy_result": "PASS",
            "symbol": "TESTIPO",
        }
    )

    assert result["status"] == "EXECUTED"

    assert (
        result["paper_trade"]["entry"]["action"]
        == "BUY"
    )

    assert (
        result["paper_trade"]["exit"]["action"]
        == "SELL"
    )

    assert runner.get_position("TESTIPO") is None
    assert runner.get_realized_pnl() == 10.0


def test_stop_loss_trade_is_replayed():
    runner = IPOPaperTradingRunner(
        backtest_runner=FakeBacktestRunner(
            {
                "company_name": "Test IPO",
                "symbol": "TESTIPO",
                "outcome": "STOP_LOSS",
                "entry_time": datetime(
                    2026,
                    8,
                    24,
                    10,
                    0,
                ),
                "entry_price": 100.0,
                "exit_time": datetime(
                    2026,
                    8,
                    24,
                    10,
                    30,
                ),
                "exit_price": 95.0,
                "reason": "Stop loss reached.",
            }
        )
    )

    result = runner.run_one(
        {
            "company_name": "Test IPO",
            "chittorgarh_ipo_id": 1,
            "strategy_result": "PASS",
            "symbol": "TESTIPO",
        }
    )

    assert result["status"] == "EXECUTED"
    assert runner.get_position("TESTIPO") is None
    assert runner.get_realized_pnl() == -5.0


def test_missing_entry_price_is_not_executed():
    runner = IPOPaperTradingRunner(
        backtest_runner=FakeBacktestRunner(
            {
                "company_name": "Test IPO",
                "symbol": "TESTIPO",
                "outcome": "TARGET",
                "entry_price": None,
            }
        )
    )

    result = runner.run_one(
        {
            "company_name": "Test IPO",
            "chittorgarh_ipo_id": 1,
            "strategy_result": "PASS",
            "symbol": "TESTIPO",
        }
    )

    assert result["status"] == "NOT_EVALUABLE"
    assert runner.get_orders() == []


def test_run_all():
    runner = IPOPaperTradingRunner(
        backtest_runner=FakeBacktestRunner(
            {
                "company_name": "Test IPO",
                "symbol": "TESTIPO",
                "outcome": "NO_TRADE",
                "reason": "No trade.",
            }
        )
    )

    results = runner.run_all(
        [
            {
                "company_name": "Test IPO",
                "chittorgarh_ipo_id": 1,
                "strategy_result": "PASS",
                "symbol": "TESTIPO",
            },
            {
                "company_name": "Test IPO 2",
                "chittorgarh_ipo_id": 2,
                "strategy_result": "PASS",
                "symbol": "TESTIPO2",
            },
        ]
    )

    assert len(results) == 2
    assert all(
        result["status"] == "NO_TRADE"
        for result in results
    )