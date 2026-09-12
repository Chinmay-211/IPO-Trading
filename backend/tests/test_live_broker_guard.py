import os
import pytest

from backend.execution.broker_interface import BrokerInterface
from backend.execution.live_broker_guard import (
    LiveBrokerGuard,
    LiveTradingSafetyViolation,
)
from backend.execution.paper_broker import PaperBroker


def test_paper_broker_implements_broker_interface():
    broker = PaperBroker()
    assert isinstance(broker, BrokerInterface)
    assert hasattr(broker, "place_order")
    assert hasattr(broker, "get_position")
    assert hasattr(broker, "get_orders")
    assert hasattr(broker, "get_realized_pnl")
    assert hasattr(broker, "reset")


def test_live_broker_guard_blocks_by_default(monkeypatch):
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.delenv("LIVE_TRADING_CONFIRMATION", raising=False)

    assert LiveBrokerGuard.is_live_trading_enabled() is False

    with pytest.raises(LiveTradingSafetyViolation) as exc_info:
        LiveBrokerGuard.enforce_live_trading_safety()

    assert "SAFETY LOCK ACTIVATED" in str(exc_info.value)


def test_live_broker_guard_blocks_partial_confirmation(monkeypatch):
    # Case 1: TRADING_MODE is LIVE but missing confirmation string
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    monkeypatch.delenv("LIVE_TRADING_CONFIRMATION", raising=False)
    assert LiveBrokerGuard.is_live_trading_enabled() is False
    with pytest.raises(LiveTradingSafetyViolation):
        LiveBrokerGuard.enforce_live_trading_safety()

    # Case 2: Confirmation string present but TRADING_MODE is PAPER
    monkeypatch.setenv("TRADING_MODE", "PAPER")
    monkeypatch.setenv("LIVE_TRADING_CONFIRMATION", "I_UNDERSTAND_REAL_MONEY_RISK")
    assert LiveBrokerGuard.is_live_trading_enabled() is False
    with pytest.raises(LiveTradingSafetyViolation):
        LiveBrokerGuard.enforce_live_trading_safety()


def test_live_broker_guard_unlocks_with_dual_confirmation(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    monkeypatch.setenv("LIVE_TRADING_CONFIRMATION", "I_UNDERSTAND_REAL_MONEY_RISK")

    assert LiveBrokerGuard.is_live_trading_enabled() is True
    # Should not raise exception
    LiveBrokerGuard.enforce_live_trading_safety()
