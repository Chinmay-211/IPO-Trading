from datetime import datetime

import pytest

from backend.services.paper_trading_runner import (
    PaperTradingRunner,
)


def test_buy():
    runner = PaperTradingRunner()

    result = runner.run_one(
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

    position = runner.get_position("TESTIPO")

    assert position is not None
    assert position["quantity"] == 10


def test_buy_then_sell():
    runner = PaperTradingRunner()

    runner.run_one(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    result = runner.run_one(
        {
            "action": "SELL",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 110.0,
        }
    )

    assert result["action"] == "SELL"
    assert result["executed"] is True
    assert runner.get_position("TESTIPO") is None
    assert runner.get_realized_pnl() == 100.0


def test_no_trade():
    runner = PaperTradingRunner()

    result = runner.run_one(
        {
            "action": "NO_TRADE",
            "reason": "Conditions not satisfied.",
        }
    )

    assert result["action"] == "NO_TRADE"
    assert result["executed"] is False
    assert result["order"] is None
    assert runner.get_orders() == []


def test_invalid_action():
    runner = PaperTradingRunner()

    with pytest.raises(ValueError):
        runner.run_one(
            {
                "action": "INVALID",
                "symbol": "TESTIPO",
                "quantity": 10,
                "price": 100.0,
            }
        )


def test_orders():
    runner = PaperTradingRunner()

    runner.run_one(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 5,
            "price": 200.0,
        }
    )

    orders = runner.get_orders()

    assert len(orders) == 1
    assert orders[0]["side"] == "BUY"
    assert orders[0]["symbol"] == "TESTIPO"
    assert orders[0]["quantity"] == 5


def test_reset():
    runner = PaperTradingRunner()

    runner.run_one(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    runner.reset()

    assert runner.get_position("TESTIPO") is None
    assert runner.get_orders() == []
    assert runner.get_realized_pnl() == 0.0