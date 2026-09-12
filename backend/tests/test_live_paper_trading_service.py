from datetime import datetime

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)


def make_service():
    broker = PaperBroker(
        initial_cash=100000
    )

    executor = StrategyExecutor(
        broker
    )

    return LivePaperTradingService(
        executor
    )


def test_enter():
    service = make_service()

    result = service.enter(
        symbol="TESTIPO",
        quantity=10,
        price=100,
        timestamp=datetime(
            2026,
            8,
            24,
            10,
            1,
        ),
    )

    assert result["action"] == "BUY"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 100

    position = service.get_position(
        "TESTIPO"
    )

    assert position["quantity"] == 10
    assert position["average_price"] == 100


def test_exit():
    service = make_service()

    service.enter(
        symbol="TESTIPO",
        quantity=10,
        price=100,
    )

    result = service.exit(
        symbol="TESTIPO",
        quantity=10,
        price=110,
    )

    assert result["action"] == "SELL"
    assert service.get_position(
        "TESTIPO"
    ) is None
    assert service.get_realized_pnl() == 100


def test_orders():
    service = make_service()

    service.enter(
        symbol="TESTIPO",
        quantity=10,
        price=100,
    )

    assert len(
        service.get_orders()
    ) == 1


def test_reset():
    service = make_service()

    service.enter(
        symbol="TESTIPO",
        quantity=10,
        price=100,
    )

    service.reset()

    assert service.get_orders() == []
    assert service.get_position(
        "TESTIPO"
    ) is None
    assert service.get_realized_pnl() == 0


def test_invalid_service():
    with pytest.raises(
        ValueError,
        match="strategy_executor is required",
    ):
        LivePaperTradingService(None)