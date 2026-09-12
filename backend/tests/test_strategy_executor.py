from datetime import datetime

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor


def test_execute_entry():
    broker = PaperBroker()
    executor = StrategyExecutor(broker)

    timestamp = datetime(
        2026,
        8,
        29,
        10,
        0,
    )

    result = executor.execute_entry(
        symbol="TESTIPO",
        quantity=10,
        price=100,
        timestamp=timestamp,
    )

    assert result["action"] == "BUY"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 100

    position = broker.get_position("TESTIPO")

    assert position is not None
    assert position["quantity"] == 10
    assert position["average_price"] == 100


def test_execute_exit():
    broker = PaperBroker()
    executor = StrategyExecutor(broker)

    executor.execute_entry(
        symbol="TESTIPO",
        quantity=10,
        price=100,
        timestamp=datetime(
            2026,
            8,
            29,
            10,
            0,
        ),
    )

    result = executor.execute_exit(
        symbol="TESTIPO",
        quantity=10,
        price=110,
        timestamp=datetime(
            2026,
            8,
            29,
            10,
            10,
        ),
    )

    assert result["action"] == "SELL"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 110

    assert broker.get_position("TESTIPO") is None
    assert broker.get_realized_pnl() == 100


def test_entry_rejects_invalid_quantity():
    executor = StrategyExecutor(PaperBroker())

    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero.",
    ):
        executor.execute_entry(
            symbol="TESTIPO",
            quantity=0,
            price=100,
        )


def test_entry_rejects_invalid_price():
    executor = StrategyExecutor(PaperBroker())

    with pytest.raises(
        ValueError,
        match="price must be greater than zero.",
    ):
        executor.execute_entry(
            symbol="TESTIPO",
            quantity=10,
            price=0,
        )


def test_exit_rejects_invalid_quantity():
    executor = StrategyExecutor(PaperBroker())

    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero.",
    ):
        executor.execute_exit(
            symbol="TESTIPO",
            quantity=0,
            price=100,
        )


def test_executor_requires_broker():
    with pytest.raises(
        ValueError,
        match="broker is required.",
    ):
        StrategyExecutor(None)


def test_orders_are_recorded():
    broker = PaperBroker()
    executor = StrategyExecutor(broker)

    executor.execute_entry(
        symbol="TESTIPO",
        quantity=5,
        price=100,
    )

    orders = broker.get_orders()

    assert len(orders) == 1
    assert orders[0]["side"] == "BUY"
    assert orders[0]["symbol"] == "TESTIPO"
    assert orders[0]["quantity"] == 5
    assert orders[0]["price"] == 100
    assert orders[0]["status"] == "FILLED"