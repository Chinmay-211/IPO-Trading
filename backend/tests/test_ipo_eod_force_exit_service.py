from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)
from backend.services.ipo_eod_force_exit_service import (
    IPOEODForceExitService,
)
from backend.services.market_session_service import (
    MarketSessionService,
)


IST = ZoneInfo("Asia/Kolkata")


def make_service():
    broker = PaperBroker()

    executor = StrategyExecutor(
        broker
    )

    paper_service = LivePaperTradingService(
        executor
    )

    execution_service = (
        IPOLivePaperExecutionService(
            paper_service
        )
    )

    session_service = MarketSessionService()

    return IPOEODForceExitService(
        execution_service,
        session_service,
    )


def timestamp(
    hour,
    minute,
):
    return datetime(
        2026,
        8,
        31,
        hour,
        minute,
        tzinfo=IST,
    )


def buy_position(service):
    service.execution_service.execute_decision(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100,
        },
        timestamp=timestamp(10, 0),
    )


def test_market_is_open_before_close():
    service = make_service()

    assert (
        service.is_market_closed(
            timestamp(15, 0)
        )
        is False
    )


def test_market_is_closed_at_1530():
    service = make_service()

    assert (
        service.is_market_closed(
            timestamp(15, 30)
        )
        is True
    )


def test_entry_allowed_during_market():
    service = make_service()

    assert (
        service.should_accept_entry(
            timestamp(10, 0)
        )
        is True
    )


def test_entry_rejected_after_market_close():
    service = make_service()

    assert (
        service.should_accept_entry(
            timestamp(15, 30)
        )
        is False
    )


def test_force_exit_closes_open_position():
    service = make_service()

    buy_position(service)

    result = service.force_exit(
        symbol="TESTIPO",
        price=105,
        timestamp=timestamp(15, 30),
    )

    assert result["action"] == "EOD_EXIT"
    assert result["executed"] is True
    assert result["eod_force_exit"] is True

    assert (
        service.execution_service.get_position(
            "TESTIPO"
        )
        is None
    )


def test_force_exit_creates_sell_order():
    service = make_service()

    buy_position(service)

    service.force_exit(
        symbol="TESTIPO",
        price=105,
        timestamp=timestamp(15, 30),
    )

    orders = (
        service.execution_service.get_orders()
    )

    assert len(orders) == 2
    assert orders[0]["side"] == "BUY"
    assert orders[1]["side"] == "SELL"


def test_force_exit_realized_pnl():
    service = make_service()

    buy_position(service)

    service.force_exit(
        symbol="TESTIPO",
        price=105,
        timestamp=timestamp(15, 30),
    )

    assert (
        service.execution_service
        .get_realized_pnl()
        == 50
    )


def test_no_position_does_not_create_order():
    service = make_service()

    result = service.force_exit(
        symbol="TESTIPO",
        price=105,
        timestamp=timestamp(15, 30),
    )

    assert result["executed"] is False
    assert result["quantity"] == 0

    assert (
        service.execution_service.get_orders()
        == []
    )


def test_session_becomes_closed_after_force_exit():
    service = make_service()

    buy_position(service)

    service.force_exit(
        symbol="TESTIPO",
        price=105,
        timestamp=timestamp(15, 30),
    )

    assert service.session_closed is True

    assert (
        service.should_accept_entry(
            timestamp(15, 29)
        )
        is False
    )


def test_close_session_without_position():
    service = make_service()

    result = service.close_session(
        timestamp(15, 30)
    )

    assert (
        result["action"]
        == "SESSION_CLOSED"
    )

    assert (
        result["executed"]
        is False
    )

    assert service.session_closed is True


def test_reset_opens_new_session():
    service = make_service()

    service.close_session(
        timestamp(15, 30)
    )

    service.reset()

    assert service.session_closed is False
    assert service.last_result is None

    assert (
        service.should_accept_entry(
            timestamp(10, 0)
        )
        is True
    )


def test_invalid_symbol_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.force_exit(
            symbol="",
            price=100,
            timestamp=timestamp(15, 30),
        )


def test_invalid_price_is_rejected():
    service = make_service()

    with pytest.raises(ValueError):
        service.force_exit(
            symbol="TESTIPO",
            price=0,
            timestamp=timestamp(15, 30),
        )


def test_invalid_timestamp_is_rejected():
    service = make_service()

    with pytest.raises(TypeError):
        service.force_exit(
            symbol="TESTIPO",
            price=100,
            timestamp="15:30",
        )