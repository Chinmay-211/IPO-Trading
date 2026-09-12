from datetime import datetime

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.execution.paper_trading_engine import (
    PaperTradingEngine,
)


def create_engine():
    broker = PaperBroker(initial_cash=100000)
    executor = StrategyExecutor(broker)
    return PaperTradingEngine(executor)


def test_buy_decision_is_executed():
    engine = create_engine()

    result = engine.execute(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        },
        timestamp=datetime(2026, 8, 24, 10, 0),
    )

    assert result["action"] == "BUY"
    assert result["executed"] is True
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 100.0

    position = engine.get_position("TESTIPO")

    assert position is not None
    assert position["quantity"] == 10
    assert position["average_price"] == 100.0


def test_sell_decision_is_executed():
    engine = create_engine()

    engine.execute(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    result = engine.execute(
        {
            "action": "SELL",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 110.0,
        }
    )

    assert result["action"] == "SELL"
    assert result["executed"] is True

    assert engine.get_position("TESTIPO") is None
    assert engine.get_realized_pnl() == 100.0


def test_no_trade_does_not_reach_broker():
    engine = create_engine()

    result = engine.execute(
        {
            "action": "NO_TRADE",
            "reason": "Strategy conditions were not satisfied.",
        }
    )

    assert result["action"] == "NO_TRADE"
    assert result["executed"] is False
    assert result["order"] is None
    assert engine.get_orders() == []


def test_invalid_action_is_rejected():
    engine = create_engine()

    with pytest.raises(ValueError):
        engine.execute(
            {
                "action": "HOLD",
                "symbol": "TESTIPO",
                "quantity": 10,
                "price": 100.0,
            }
        )


def test_missing_action_is_rejected():
    engine = create_engine()

    with pytest.raises(ValueError):
        engine.execute(
            {
                "symbol": "TESTIPO",
                "quantity": 10,
                "price": 100.0,
            }
        )


def test_orders_are_available():
    engine = create_engine()

    engine.execute(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 5,
            "price": 200.0,
        }
    )

    orders = engine.get_orders()

    assert len(orders) == 1
    assert orders[0]["symbol"] == "TESTIPO"
    assert orders[0]["side"] == "BUY"
    assert orders[0]["quantity"] == 5


def test_reset_clears_paper_trading_state():
    engine = create_engine()

    engine.execute(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    engine.reset()

    assert engine.get_position("TESTIPO") is None
    assert engine.get_orders() == []
    assert engine.get_realized_pnl() == 0.0