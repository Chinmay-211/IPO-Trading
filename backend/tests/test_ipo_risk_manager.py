import pytest

from backend.services.ipo_risk_manager import (
    IPORiskManager,
)


def test_risk_manager_allows_entry_within_limits():
    risk = IPORiskManager(
        max_daily_loss=5000.0,
        max_capital_per_ipo=50000.0,
        max_concurrent_positions=2,
    )

    allowed, reason = risk.can_enter(
        symbol="SWIGGY",
        price=400.0,
        quantity=10,
        current_realized_pnl=-500.0,
        active_positions={},
    )

    assert allowed is True
    assert reason == "APPROVED"


def test_risk_manager_blocks_entry_when_daily_loss_limit_hit():
    risk = IPORiskManager(max_daily_loss=2000.0)

    # Realized loss of -2500 exceeds max_daily_loss of 2000
    allowed, reason = risk.can_enter(
        symbol="NTPCGREEN",
        price=100.0,
        quantity=10,
        current_realized_pnl=-2500.0,
    )

    assert allowed is False
    assert reason == "DAILY_LOSS_LIMIT_REACHED"
    assert risk.trading_halted is True

    # Subsequent entry is also blocked due to halt
    allowed2, reason2 = risk.can_enter(
        symbol="ANOTHERIPO",
        price=100.0,
        quantity=5,
        current_realized_pnl=0.0,
    )
    assert allowed2 is False
    assert "TRADING_HALTED" in reason2


def test_risk_manager_blocks_entry_when_max_positions_reached():
    risk = IPORiskManager(max_concurrent_positions=2)

    active_positions = {
        "IPO_A": {"symbol": "IPO_A", "quantity": 10, "average_price": 100.0},
        "IPO_B": {"symbol": "IPO_B", "quantity": 20, "average_price": 200.0},
    }

    # Attempting to enter a 3rd new position
    allowed, reason = risk.can_enter(
        symbol="IPO_C",
        price=50.0,
        quantity=10,
        active_positions=active_positions,
    )

    assert allowed is False
    assert reason == "MAX_POSITIONS_REACHED"

    # But adding to an already open position is not blocked by the new position limit
    allowed_existing, _ = risk.can_enter(
        symbol="IPO_A",
        price=100.0,
        quantity=5,
        active_positions=active_positions,
    )
    assert allowed_existing is True


def test_risk_manager_blocks_entry_exceeding_max_capital():
    risk = IPORiskManager(max_capital_per_ipo=10000.0)

    # 150.0 * 100 = 15,000 > 10,000
    allowed, reason = risk.can_enter(
        symbol="EXPENSIVE_IPO",
        price=150.0,
        quantity=100,
    )

    assert allowed is False
    assert reason == "MAX_CAPITAL_EXCEEDED"


def test_risk_manager_always_permits_exits():
    risk = IPORiskManager(max_daily_loss=1000.0)
    risk.trading_halted = True

    # Exits are ALWAYS permitted even when trading is halted
    allowed, reason = risk.can_exit(symbol="ANY_IPO")
    assert allowed is True
    assert reason == "EXIT_APPROVED"
