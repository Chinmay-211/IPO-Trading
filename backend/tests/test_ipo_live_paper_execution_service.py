from datetime import datetime

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)


def make_service():
    broker = PaperBroker(initial_cash=100000)
    executor = StrategyExecutor(broker)
    paper_service = LivePaperTradingService(executor)

    return IPOLivePaperExecutionService(
        paper_service
    )


def test_buy_decision_executes():
    service = make_service()

    result = service.execute_decision(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        },
        timestamp=datetime(2026, 8, 31, 9, 20),
    )

    assert result["action"] == "BUY"
    assert result["executed"] is True
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 100.0
    assert result["order"] is not None


def test_no_trade_does_not_execute():
    service = make_service()

    result = service.execute_decision(
        {
            "action": "NO_TRADE",
            "symbol": "TESTIPO",
            "reason": "Strategy conditions not met.",
        }
    )

    assert result["executed"] is False
    assert result["order"] is None
    assert service.get_orders() == []


def test_hold_does_not_execute():
    service = make_service()

    result = service.execute_decision(
        {
            "action": "HOLD",
            "symbol": "TESTIPO",
        }
    )

    assert result["executed"] is False
    assert result["order"] is None
    assert service.get_orders() == []


def test_invalid_action_does_not_execute():
    service = make_service()

    result = service.execute_decision(
        {
            "action": "INVALID",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    assert result["executed"] is False
    assert result["order"] is None
    assert service.get_orders() == []


def test_missing_symbol_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.execute_decision(
            {
                "action": "BUY",
                "quantity": 10,
                "price": 100.0,
            }
        )


def test_missing_quantity_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.execute_decision(
            {
                "action": "BUY",
                "symbol": "TESTIPO",
                "price": 100.0,
            }
        )


def test_invalid_quantity_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.execute_decision(
            {
                "action": "BUY",
                "symbol": "TESTIPO",
                "quantity": 0,
                "price": 100.0,
            }
        )


def test_invalid_price_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.execute_decision(
            {
                "action": "BUY",
                "symbol": "TESTIPO",
                "quantity": 10,
                "price": 0,
            }
        )


def test_realized_pnl_is_available():
    service = make_service()

    service.execute_decision(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    service.execute_decision(
        {
            "action": "SELL",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 110.0,
        }
    )

    assert service.get_realized_pnl() == 100.0


def test_reset_clears_paper_execution_state():
    service = make_service()

    service.execute_decision(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    assert service.get_orders()

    service.reset()

    assert service.get_orders() == []