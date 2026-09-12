from datetime import datetime

import pytest

from backend.execution.paper_broker import PaperBroker


def test_paper_broker_buy_sell_and_pnl():
    broker = PaperBroker()

    buy = broker.place_order(
        symbol="HORIZONIND",
        side="BUY",
        quantity=100,
        price=60.00,
        timestamp=datetime(2026, 8, 24, 10, 15),
    )

    assert buy["status"] == "FILLED"
    assert buy["side"] == "BUY"
    assert buy["quantity"] == 100
    assert buy["price"] == 60.00

    position = broker.get_position("HORIZONIND")

    assert position is not None
    assert position["symbol"] == "HORIZONIND"
    assert position["quantity"] == 100
    assert position["average_price"] == 60.00

    sell = broker.place_order(
        symbol="HORIZONIND",
        side="SELL",
        quantity=100,
        price=66.00,
        timestamp=datetime(2026, 8, 24, 10, 30),
    )

    assert sell["status"] == "FILLED"
    assert sell["side"] == "SELL"

    assert broker.get_position("HORIZONIND") is None
    assert broker.get_realized_pnl() == 600.00


def test_paper_broker_average_price():
    broker = PaperBroker()

    broker.place_order(
        symbol="TESTIPO",
        side="BUY",
        quantity=100,
        price=50.00,
    )

    broker.place_order(
        symbol="TESTIPO",
        side="BUY",
        quantity=100,
        price=60.00,
    )

    position = broker.get_position("TESTIPO")

    assert position is not None
    assert position["quantity"] == 200
    assert position["average_price"] == 55.00


def test_paper_broker_cannot_sell_without_position():
    broker = PaperBroker()

    with pytest.raises(ValueError, match="No open position"):
        broker.place_order(
            symbol="TESTIPO",
            side="SELL",
            quantity=10,
            price=50.00,
        )


def test_paper_broker_cannot_oversell():
    broker = PaperBroker()

    broker.place_order(
        symbol="TESTIPO",
        side="BUY",
        quantity=10,
        price=50.00,
    )

    with pytest.raises(ValueError, match="only 10 are available"):
        broker.place_order(
            symbol="TESTIPO",
            side="SELL",
            quantity=11,
            price=55.00,
        )


def test_paper_broker_rejects_invalid_orders():
    broker = PaperBroker()

    with pytest.raises(ValueError, match="symbol is required"):
        broker.place_order(
            symbol="",
            side="BUY",
            quantity=10,
            price=50.00,
        )

    with pytest.raises(ValueError, match="Unsupported order side"):
        broker.place_order(
            symbol="TESTIPO",
            side="HOLD",
            quantity=10,
            price=50.00,
        )

    with pytest.raises(ValueError, match="quantity must be greater"):
        broker.place_order(
            symbol="TESTIPO",
            side="BUY",
            quantity=0,
            price=50.00,
        )

    with pytest.raises(ValueError, match="price must be greater"):
        broker.place_order(
            symbol="TESTIPO",
            side="BUY",
            quantity=10,
            price=0,
        )


def test_paper_broker_orders_are_recorded():
    broker = PaperBroker()

    broker.place_order(
        symbol="TESTIPO",
        side="BUY",
        quantity=25,
        price=100.00,
    )

    broker.place_order(
        symbol="TESTIPO",
        side="SELL",
        quantity=25,
        price=105.00,
    )

    orders = broker.get_orders()

    assert len(orders) == 2
    assert orders[0]["side"] == "BUY"
    assert orders[1]["side"] == "SELL"
    assert orders[0]["status"] == "FILLED"
    assert orders[1]["status"] == "FILLED"


def test_paper_broker_reset():
    broker = PaperBroker()

    broker.place_order(
        symbol="TESTIPO",
        side="BUY",
        quantity=10,
        price=100.00,
    )

    broker.reset()

    assert broker.get_orders() == []
    assert broker.get_position("TESTIPO") is None
    assert broker.get_realized_pnl() == 0.0