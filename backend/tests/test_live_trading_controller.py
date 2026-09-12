from datetime import datetime

import pytest

from backend.execution.live_trading_controller import (
    LiveTradingController,
)
from backend.execution.paper_broker import PaperBroker
from backend.execution.live_broker import LiveBroker


def test_controller_executes_entry_with_paper_broker():
    broker = PaperBroker(initial_cash=100000)

    controller = LiveTradingController(
        broker=broker,
    )

    result = controller.execute_entry(
        symbol="TESTIPO",
        quantity=10,
        price=100.0,
        timestamp=datetime(2026, 8, 24, 10, 0),
    )

    assert result["action"] == "BUY"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10

    position = controller.get_position("TESTIPO")

    assert position is not None
    assert position["quantity"] == 10
    assert position["average_price"] == 100.0


def test_controller_executes_exit_with_paper_broker():
    broker = PaperBroker(initial_cash=100000)

    controller = LiveTradingController(
        broker=broker,
    )

    controller.execute_entry(
        symbol="TESTIPO",
        quantity=10,
        price=100.0,
    )

    result = controller.execute_exit(
        symbol="TESTIPO",
        quantity=10,
        price=110.0,
    )

    assert result["action"] == "SELL"
    assert controller.get_position("TESTIPO") is None
    assert controller.get_realized_pnl() == 100.0


def test_controller_rejects_invalid_entry():
    broker = PaperBroker(initial_cash=100000)

    controller = LiveTradingController(
        broker=broker,
    )

    with pytest.raises(ValueError):
        controller.execute_entry(
            symbol="TESTIPO",
            quantity=0,
            price=100.0,
        )


def test_controller_rejects_invalid_exit():
    broker = PaperBroker(initial_cash=100000)

    controller = LiveTradingController(
        broker=broker,
    )

    with pytest.raises(ValueError):
        controller.execute_exit(
            symbol="TESTIPO",
            quantity=0,
            price=100.0,
        )


def test_controller_live_broker_remains_blocked():
    broker = LiveBroker()

    controller = LiveTradingController(
        broker=broker,
        live_enabled=True,
    )

    with pytest.raises(RuntimeError, match="Live trading is not enabled"):
        controller.execute_entry(
            symbol="TESTIPO",
            quantity=10,
            price=100.0,
        )


def test_controller_requires_broker():
    with pytest.raises(ValueError, match="broker is required"):
        LiveTradingController(None)


def test_controller_rejects_invalid_live_flag():
    broker = PaperBroker(initial_cash=100000)

    with pytest.raises(
        ValueError,
        match="live_enabled must be a boolean",
    ):
        LiveTradingController(
            broker=broker,
            live_enabled="yes",
        )