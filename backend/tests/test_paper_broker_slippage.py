from datetime import datetime

import pytest

from backend.execution.paper_broker import PaperBroker


def test_zero_slippage_maintains_exact_requested_price():
    broker = PaperBroker(slippage_pct=0.0)

    buy_order = broker.place_order(
        symbol="RELIANCE",
        side="BUY",
        quantity=10,
        price=100.0,
        timestamp=datetime(2026, 8, 24, 10, 0),
    )

    assert buy_order["price"] == 100.0

    sell_order = broker.place_order(
        symbol="RELIANCE",
        side="SELL",
        quantity=10,
        price=110.0,
        timestamp=datetime(2026, 8, 24, 10, 5),
    )

    assert sell_order["price"] == 110.0
    # Exact PnL: (110 - 100) * 10 = 100.0
    assert broker.get_realized_pnl() == 100.0


def test_positive_slippage_fills_buy_higher_and_sell_lower():
    # 0.1% slippage (0.001)
    broker = PaperBroker(slippage_pct=0.001)

    buy_order = broker.place_order(
        symbol="INFY",
        side="BUY",
        quantity=100,
        price=1000.0,
        timestamp=datetime(2026, 8, 24, 10, 0),
    )

    # 1000 * 1.001 = 1001.0
    assert buy_order["price"] == 1001.0
    pos = broker.get_position("INFY")
    assert pos["average_price"] == 1001.0

    sell_order = broker.place_order(
        symbol="INFY",
        side="SELL",
        quantity=100,
        price=1100.0,
        timestamp=datetime(2026, 8, 24, 10, 5),
    )

    # 1100 * (1 - 0.001) = 1098.9
    assert sell_order["price"] == 1098.9

    # Realized PnL: (1098.9 - 1001.0) * 100 = 9790.0 (less than 10,000 due to slippage)
    assert round(broker.get_realized_pnl(), 2) == 9790.0
