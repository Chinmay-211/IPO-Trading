from datetime import datetime

import pytest

from backend.execution.execution_service import ExecutionService
from backend.execution.paper_broker import PaperBroker


def test_buy():
    broker = PaperBroker()
    service = ExecutionService(broker)

    result = service.buy(
        symbol="TESTIPO",
        quantity=10,
        price=100.0,
        timestamp=datetime(2026, 8, 29, 10, 0),
    )

    assert result["side"] == "BUY"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10

    position = service.get_position("TESTIPO")

    assert position["quantity"] == 10
    assert position["average_price"] == 100.0


def test_sell():
    broker = PaperBroker()
    service = ExecutionService(broker)

    service.buy(
        symbol="TESTIPO",
        quantity=10,
        price=100.0,
    )

    result = service.sell(
        symbol="TESTIPO",
        quantity=10,
        price=110.0,
    )

    assert result["side"] == "SELL"
    assert service.get_position("TESTIPO") is None
    assert service.get_realized_pnl() == 100.0


def test_invalid_buy_is_rejected():
    broker = PaperBroker()
    service = ExecutionService(broker)

    with pytest.raises(ValueError):
        service.buy(
            symbol="TESTIPO",
            quantity=0,
            price=100.0,
        )


def test_invalid_sell_is_rejected():
    broker = PaperBroker()
    service = ExecutionService(broker)

    with pytest.raises(ValueError):
        service.sell(
            symbol="TESTIPO",
            quantity=10,
            price=0,
        )


def test_orders_are_available():
    broker = PaperBroker()
    service = ExecutionService(broker)

    service.buy(
        symbol="TESTIPO",
        quantity=5,
        price=50.0,
    )

    orders = service.get_orders()

    assert len(orders) == 1
    assert orders[0]["side"] == "BUY"


def test_reset():
    broker = PaperBroker()
    service = ExecutionService(broker)

    service.buy(
        symbol="TESTIPO",
        quantity=5,
        price=50.0,
    )

    service.reset()

    assert service.get_orders() == []
    assert service.get_position("TESTIPO") is None


def test_execution_service_requires_broker():
    with pytest.raises(ValueError, match="broker is required"):
        ExecutionService(None)