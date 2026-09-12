from datetime import datetime

import pytest

from backend.execution.execution_service import ExecutionService
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_paper_trading_batch import (
    IPOPaperTradingBatch,
)
from backend.services.ipo_trading_orchestrator import (
    IPOTradingOrchestrator,
)


def make_batch():
    broker = PaperBroker(
        initial_cash=100000
    )

    execution_service = ExecutionService(
        broker
    )

    strategy_executor = StrategyExecutor(
        broker
    )

    orchestrator = IPOTradingOrchestrator(
        execution_service=execution_service,
        strategy_executor=strategy_executor,
    )

    return IPOPaperTradingBatch(orchestrator)


def make_ipo():
    return {
        "id": 201,
        "company_name": "Test IPO Limited",
        "symbol": "TESTIPO",
        "listing_date": "2026-08-24",
    }


def make_candles():
    return [
        {
            "timestamp": datetime(
                2026,
                8,
                24,
                10,
                1,
            ),
            "open": 100,
            "high": 102,
            "low": 99,
            "close": 101,
            "volume": 1000,
        },
        {
            "timestamp": datetime(
                2026,
                8,
                24,
                10,
                2,
            ),
            "open": 101,
            "high": 111,
            "low": 100,
            "close": 110,
            "volume": 1500,
        },
    ]


def test_run_one_target():
    batch = make_batch()

    result = batch.run_one(
        ipo=make_ipo(),
        candles=make_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["ipo_id"] == 201
    assert result["company_name"] == "Test IPO Limited"
    assert result["symbol"] == "TESTIPO"
    assert result["listing_date"] == "2026-08-24"

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "TARGET"

    assert result["profit_loss"] == 100
    assert result["profit_loss_percent"] == 10


def test_run_one_stop_loss():
    batch = make_batch()

    candles = [
        {
            "timestamp": datetime(
                2026,
                8,
                24,
                10,
                1,
            ),
            "open": 100,
            "high": 101,
            "low": 94,
            "close": 95,
            "volume": 1000,
        }
    ]

    result = batch.run_one(
        ipo=make_ipo(),
        candles=candles,
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "STOP_LOSS"

    assert result["profit_loss"] == -50
    assert result["profit_loss_percent"] == -5


def test_run_one_can_remain_open():
    batch = make_batch()

    candles = [
        {
            "timestamp": datetime(
                2026,
                8,
                24,
                10,
                1,
            ),
            "open": 100,
            "high": 104,
            "low": 98,
            "close": 103,
            "volume": 1000,
        }
    ]

    result = batch.run_one(
        ipo=make_ipo(),
        candles=candles,
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "OPEN"
    assert result["exit"] is None
    assert result["exit_reason"] is None


def test_run_batch():
    batch = make_batch()

    trades = [
        {
            "ipo": make_ipo(),
            "candles": make_candles(),
            "quantity": 10,
            "entry_price": 100,
            "target_price": 110,
            "stop_loss_price": 95,
        },
        {
            "ipo": {
                "id": 202,
                "company_name": "Second IPO Limited",
                "symbol": "SECONDIPO",
                "listing_date": "2026-08-24",
            },
            "candles": [
                {
                    "timestamp": datetime(
                        2026,
                        8,
                        24,
                        10,
                        1,
                    ),
                    "open": 100,
                    "high": 101,
                    "low": 94,
                    "close": 95,
                    "volume": 1000,
                }
            ],
            "quantity": 5,
            "entry_price": 100,
            "target_price": 110,
            "stop_loss_price": 95,
        },
    ]

    results = batch.run_batch(trades)

    assert len(results) == 2

    assert results[0]["status"] == "CLOSED"
    assert results[0]["exit_reason"] == "TARGET"

    assert results[1]["status"] == "CLOSED"
    assert results[1]["exit_reason"] == "STOP_LOSS"


def test_invalid_ipo():
    batch = make_batch()

    with pytest.raises(
        ValueError,
        match="IPO trading symbol is required",
    ):
        batch.run_one(
            ipo={},
            candles=[],
            quantity=10,
            entry_price=100,
            target_price=110,
            stop_loss_price=95,
        )


def test_invalid_trades():
    batch = make_batch()

    with pytest.raises(
        ValueError,
        match="trades must be a list",
    ):
        batch.run_batch(None)