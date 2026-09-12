from datetime import datetime, time
import pytest

from backend.collectors.market_data.angel_one_instrument_resolver import AngelOneInstrumentResolver
from backend.services.ipo_listing_day_orchestrator import IPOListingDayOrchestrator
from backend.services.ipo_risk_manager import IPORiskManager
from backend.services.market_session_service import MarketSessionService


class DummyResolver(AngelOneInstrumentResolver):
    def __init__(self):
        self.instruments = {
            "RISKIPO": {"token": "1001", "symbol": "RISKIPO", "name": "RISKIPO LTD"},
            "SLIPIPO": {"token": "1002", "symbol": "SLIPIPO", "name": "SLIPIPO LTD"},
        }

    def find(self, symbol: str):
        sym = symbol.strip().upper()
        if sym in self.instruments:
            return self.instruments[sym]
        raise ValueError(f"Unknown {symbol}")


def test_orchestrator_passes_slippage_to_brokers():
    resolver = DummyResolver()
    session_svc = MarketSessionService.for_ipo_listing(
        listing_open=time(10, 0),
        market_close=time(15, 30),
    )
    # 0.5% slippage
    orchestrator = IPOListingDayOrchestrator(
        instrument_resolver=resolver,
        session_service=session_svc,
        default_quantity=10,
        slippage_pct=0.005,
    )
    prepared = orchestrator.prepare_session([{"symbol": "SLIPIPO"}])
    assert prepared == ["SLIPIPO"]

    broker = orchestrator.brokers["SLIPIPO"]
    assert broker.slippage_pct == 0.005

    report = orchestrator.generate_session_report()
    assert report["slippage_pct"] == 0.005
    assert report["risk_manager_active"] is False


def test_orchestrator_blocks_buy_when_risk_limit_exceeded():
    resolver = DummyResolver()
    session_svc = MarketSessionService.for_ipo_listing(
        listing_open=time(10, 0),
        market_close=time(15, 30),
    )
    # Max capital per IPO is 500, but 10 qty * 100 price = 1000 -> Should block entry!
    risk_mgr = IPORiskManager(max_capital_per_ipo=500.0)
    orchestrator = IPOListingDayOrchestrator(
        instrument_resolver=resolver,
        session_service=session_svc,
        default_quantity=10,
        risk_manager=risk_mgr,
    )
    orchestrator.prepare_session([{"symbol": "RISKIPO"}])
    orchestrator.start()

    # Feed 1-min ticks to complete first candle (10:00 - 10:01)
    base_time = datetime(2026, 8, 31, 10, 0, 0)
    # Tick 1
    orchestrator.process_tick({"symbol": "RISKIPO", "price": 100.0, "volume": 50, "timestamp": base_time})
    # Tick 2 - next minute forces candle completion & strategy evaluation
    next_min = datetime(2026, 8, 31, 10, 1, 0)
    orchestrator.process_tick({"symbol": "RISKIPO", "price": 105.0, "volume": 100, "timestamp": next_min})

    # Strategy may emit BUY on breakout, but risk manager blocks it because 10 * 105 > 500
    broker = orchestrator.brokers["RISKIPO"]
    assert len(broker.get_orders()) == 0  # No orders placed due to risk limit!
    assert broker.get_position("RISKIPO") is None

    report = orchestrator.generate_session_report()
    assert report["risk_manager_active"] is True
