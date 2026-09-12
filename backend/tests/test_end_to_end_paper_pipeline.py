from datetime import datetime

from backend.execution.execution_service import ExecutionService
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_screening_paper_pipeline import (
    IPOScreeningPaperPipeline,
)
from backend.services.ipo_strategy_paper_runner import (
    IPOStrategyPaperRunner,
)
from backend.services.ipo_paper_trading_batch import (
    IPOPaperTradingBatch,
)
from backend.services.ipo_trading_orchestrator import (
    IPOTradingOrchestrator,
)


def build_pipeline():
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

    runner = IPOStrategyPaperRunner(
        batch
    )

    return (
        IPOScreeningPaperPipeline(runner),
        broker,
    )


def make_ipo():
    return {
        "id": 999,
        "company_name": "End To End IPO",
        "symbol": "E2EIPO",
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
            "high": 112,
            "low": 99,
            "close": 110,
            "volume": 5000,
        }
    ]


def test_end_to_end_pass_to_target():
    pipeline, broker = build_pipeline()

    result = pipeline.run_one(
        ipo=make_ipo(),
        screening={
            "status": "PASS",
            "passed": True,
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

    assert broker.get_position("E2EIPO") is None
    assert broker.get_realized_pnl() == 100

    orders = broker.get_orders()

    assert len(orders) == 2
    assert orders[0]["side"] == "BUY"
    assert orders[1]["side"] == "SELL"


def test_end_to_end_failed_screening_no_order():
    pipeline, broker = build_pipeline()

    result = pipeline.run_one(
        ipo=make_ipo(),
        screening={
            "status": "FAIL",
            "passed": False,
        },
        candles=make_candles(),
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
    )

    assert result["status"] == "NO_TRADE"
    assert broker.get_orders() == []
    assert broker.get_position("E2EIPO") is None
    assert broker.get_realized_pnl() == 0