import pytest

from backend.execution.live_broker import LiveBroker


def test_live_broker_disabled_by_default():
    broker = LiveBroker()

    assert broker.enabled is False


def test_live_order_is_blocked():
    broker = LiveBroker()

    with pytest.raises(RuntimeError, match="Live trading is disabled"):
        broker.place_order(
            symbol="TEST",
            side="BUY",
            quantity=10,
            price=100.0,
        )


def test_live_position_is_blocked():
    broker = LiveBroker()

    with pytest.raises(RuntimeError, match="Live trading is disabled"):
        broker.get_position("TEST")


def test_live_pnl_is_blocked():
    broker = LiveBroker()

    with pytest.raises(RuntimeError, match="Live trading is disabled"):
        broker.get_realized_pnl()


def test_live_orders_start_empty():
    broker = LiveBroker()

    assert broker.get_orders() == []


def test_live_reset():
    broker = LiveBroker()

    broker.orders.append(
        {
            "symbol": "TEST",
            "side": "BUY",
        }
    )

    broker.reset()

    assert broker.get_orders() == []


def test_enabled_live_broker_still_blocks_unimplemented_order():
    broker = LiveBroker(enabled=True)

    with pytest.raises(
        NotImplementedError,
        match="not implemented yet",
    ):
        broker.place_order(
            symbol="TEST",
            side="BUY",
            quantity=10,
            price=100.0,
        )