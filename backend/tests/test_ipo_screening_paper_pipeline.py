from datetime import datetime

import pytest

from backend.execution.execution_service import ExecutionService
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_paper_trading_batch import (
    IPOPaperTradingBatch,
)
from backend.services.ipo_screening_paper_pipeline import (
    IPOScreeningPaperPipeline,
)
from backend.services.ipo_strategy_paper_runner import (
    IPOStrategyPaperRunner,
)
from backend.services.ipo_trading_orchestrator import (
    IPOTradingOrchestrator,
)


def make_pipeline():
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

    paper_runner = IPOStrategyPaperRunner(
        batch
    )

    return IPOScreeningPaperPipeline(
        paper_runner
    )


def ipo(symbol="TESTIPO", ipo_id=1):
    return {
        "id": ipo_id,
        "company_name": "Test IPO",
        "symbol": symbol,
        "listing_date": "2026-08-24",
    }


def target_candles():
    return [
        {
            "timestamp": datetime(
                2026, 8, 24, 10, 1
            ),
            "open": 100,
            "high": 111,
            "low": 99,
            "close": 110,
            "volume": 1000,
        }
    ]


def stop_loss_candles():
    return [
        {
            "timestamp": datetime(
                2026, 8, 24, 10, 1
            ),
            "open": 100,
            "high": 101,
            "low": 94,
            "close": 95,
            "volume": 1000,
        }
    ]


def test_passed_ipo_reaches_paper_execution():
    pipeline = make_pipeline()

    result = pipeline.run_one(
        ipo=ipo(),
        screening={"status": "PASS"},
        candles=target_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "TARGET"
    assert result["profit_loss"] == 100


def test_failed_ipo_does_not_trade():
    pipeline = make_pipeline()

    result = pipeline.run_one(
        ipo=ipo(),
        screening={"status": "FAIL"},
        candles=target_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "NO_TRADE"


def test_batch_and_summary():
    pipeline = make_pipeline()

    results = pipeline.run_batch(
        [
            {
                "ipo": ipo("TARGETIPO", 1),
                "screening": {"status": "PASS"},
                "candles": target_candles(),
                "quantity": 10,
                "entry_price": 100,
                "target_price": 110,
                "stop_loss_price": 95,
            },
            {
                "ipo": ipo("STOPIPO", 2),
                "screening": {"status": "PASS"},
                "candles": stop_loss_candles(),
                "quantity": 10,
                "entry_price": 100,
                "target_price": 110,
                "stop_loss_price": 95,
            },
            {
                "ipo": ipo("FAILIPO", 3),
                "screening": {"status": "FAIL"},
                "candles": target_candles(),
                "quantity": 10,
                "entry_price": 100,
                "target_price": 110,
                "stop_loss_price": 95,
            },
        ]
    )

    summary = pipeline.summarize(results)

    assert len(results) == 3
    assert summary["total"] == 3
    assert summary["closed"] == 2
    assert summary["target"] == 1
    assert summary["stop_loss"] == 1
    assert summary["no_trade"] == 1
    assert summary["open"] == 0
    assert summary["total_profit_loss"] == 50


def test_invalid_opportunities():
    pipeline = make_pipeline()

    with pytest.raises(
        ValueError,
        match="opportunities must be a list",
    ):
        pipeline.run_batch(None)


def test_invalid_ipo():
    pipeline = make_pipeline()

    with pytest.raises(
        ValueError,
        match="ipo must be a dictionary",
    ):
        pipeline.run_one(
            ipo=None,
            screening={"status": "PASS"},
            candles=[],
            quantity=10,
            entry_price=100,
            target_price=110,
            stop_loss_price=95,
        )