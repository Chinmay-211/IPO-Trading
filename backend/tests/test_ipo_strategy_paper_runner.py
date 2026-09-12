from datetime import datetime

import pytest

from backend.execution.execution_service import ExecutionService
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_paper_trading_batch import (
    IPOPaperTradingBatch,
)
from backend.services.ipo_strategy_paper_runner import (
    IPOStrategyPaperRunner,
)
from backend.services.ipo_trading_orchestrator import (
    IPOTradingOrchestrator,
)


def make_runner():
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

    batch = IPOPaperTradingBatch(
        orchestrator
    )

    return IPOStrategyPaperRunner(batch)


def make_ipo():
    return {
        "id": 301,
        "company_name": "Screened IPO Limited",
        "symbol": "SCREENIPO",
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


def test_passed_ipo_is_paper_traded():
    runner = make_runner()

    result = runner.run_one(
        ipo=make_ipo(),
        screening={
            "status": "PASS",
        },
        candles=make_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "TARGET"
    assert result["profit_loss"] == 100


def test_failed_ipo_is_not_traded():
    runner = make_runner()

    result = runner.run_one(
        ipo=make_ipo(),
        screening={
            "status": "FAIL",
        },
        candles=make_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "NO_TRADE"
    assert (
        result["reason"]
        == "IPO did not pass the screening strategy."
    )


def test_boolean_passed_is_supported():
    runner = make_runner()

    result = runner.run_one(
        ipo=make_ipo(),
        screening={
            "passed": True,
        },
        candles=make_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "CLOSED"


def test_boolean_eligible_is_supported():
    runner = make_runner()

    result = runner.run_one(
        ipo=make_ipo(),
        screening={
            "eligible": True,
        },
        candles=make_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "CLOSED"


def test_batch():
    runner = make_runner()

    opportunities = [
        {
            "ipo": make_ipo(),
            "screening": {
                "status": "PASS",
            },
            "candles": make_candles(),
            "quantity": 10,
            "entry_price": 100,
            "target_price": 110,
            "stop_loss_price": 95,
        },
        {
            "ipo": {
                "id": 302,
                "company_name": "Rejected IPO",
                "symbol": "REJECTIPO",
                "listing_date": "2026-08-24",
            },
            "screening": {
                "status": "FAIL",
            },
            "candles": make_candles(),
            "quantity": 10,
            "entry_price": 100,
            "target_price": 110,
            "stop_loss_price": 95,
        },
    ]

    results = runner.run_batch(
        opportunities
    )

    assert len(results) == 2
    assert results[0]["status"] == "CLOSED"
    assert results[1]["status"] == "NO_TRADE"


def test_invalid_ipo():
    runner = make_runner()

    with pytest.raises(
        ValueError,
        match="ipo must be a dictionary",
    ):
        runner.run_one(
            ipo=None,
            screening={"status": "PASS"},
            candles=[],
            quantity=10,
            entry_price=100,
            target_price=110,
            stop_loss_price=95,
        )


def test_invalid_screening():
    runner = make_runner()

    with pytest.raises(
        ValueError,
        match="screening must be a dictionary",
    ):
        runner.run_one(
            ipo=make_ipo(),
            screening=None,
            candles=[],
            quantity=10,
            entry_price=100,
            target_price=110,
            stop_loss_price=95,
        )