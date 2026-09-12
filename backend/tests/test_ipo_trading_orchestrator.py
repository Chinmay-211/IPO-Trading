from datetime import datetime

import pytest

from backend.execution.execution_service import ExecutionService
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_trading_orchestrator import (
    IPOTradingOrchestrator,
)


def make_orchestrator():
    broker = PaperBroker(initial_cash=100000)

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

    return orchestrator, broker


def test_target_exit():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 105,
                "low": 99,
            },
            {
                "timestamp": datetime(2026, 8, 29, 10, 2),
                "high": 111,
                "low": 104,
            },
        ],
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "TARGET"
    assert result["profit_loss"] == 100
    assert result["profit_loss_percent"] == 10
    assert broker.get_position("TEST") is None


def test_stop_loss_exit():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 101,
                "low": 96,
            },
            {
                "timestamp": datetime(2026, 8, 29, 10, 2),
                "high": 98,
                "low": 94,
            },
        ],
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "STOP_LOSS"
    assert result["profit_loss"] == -50
    assert result["profit_loss_percent"] == -5
    assert broker.get_position("TEST") is None


def test_position_remains_open():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 105,
                "low": 99,
            }
        ],
    )

    assert result["status"] == "OPEN"
    assert result["exit"] is None
    assert broker.get_position("TEST")["quantity"] == 10


def test_target_has_priority_over_nothing():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=5,
        entry_price=100,
        target_price=105,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 106,
                "low": 100,
            }
        ],
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "TARGET"
    assert result["profit_loss"] == 25


def test_stop_loss_priority_when_both_levels_hit():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=5,
        entry_price=100,
        target_price=105,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 106,
                "low": 94,
            }
        ],
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "STOP_LOSS"
    assert result["profit_loss"] == -25


def test_invalid_symbol():
    orchestrator, _ = make_orchestrator()

    with pytest.raises(ValueError, match="symbol is required"):
        orchestrator.execute_trade(
            symbol="",
            quantity=10,
            entry_price=100,
            target_price=110,
            stop_loss_price=95,
            candles=[],
        )


def test_invalid_candles():
    orchestrator, _ = make_orchestrator()

    with pytest.raises(ValueError, match="candles must be a list"):
        orchestrator.execute_trade(
            symbol="TEST",
            quantity=10,
            entry_price=100,
            target_price=110,
            stop_loss_price=95,
            candles=None,
        )