from datetime import datetime, time
from unittest.mock import Mock

import pytest

from backend.services.ipo_listing_day_orchestrator import (
    IPOListingDayOrchestrator,
)
from backend.services.market_session_service import (
    MarketSessionService,
)


class FakeResolver:
    """Mock instrument resolver returning canned tokens."""

    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    def find(self, symbol: str, exchange: str = "NSE") -> dict:
        sym = symbol.upper().strip()
        if sym in self.mapping:
            return {
                "token": self.mapping[sym],
                "symbol": f"{sym}-EQ",
                "exch_seg": exchange,
            }
        raise ValueError(f"Unknown symbol: {symbol}")


def test_orchestrator_prepares_session_and_resolves_tokens():
    resolver = FakeResolver({"SWIGGY": "12345", "NTPCGREEN": "67890"})
    orchestrator = IPOListingDayOrchestrator(instrument_resolver=resolver)

    candidates = [
        {"symbol": "SWIGGY", "company_name": "Swiggy Limited"},
        {"symbol": "NTPCGREEN", "company_name": "NTPC Green Energy Limited"},
        {"invalid": "entry"},  # Missing symbol, should be skipped
    ]

    symbols = orchestrator.prepare_session(candidates)

    assert symbols == ["SWIGGY", "NTPCGREEN"]
    assert orchestrator.token_to_symbol["12345"] == "SWIGGY"
    assert orchestrator.token_to_symbol["67890"] == "NTPCGREEN"
    assert "SWIGGY" in orchestrator.engine.pipelines
    assert "NTPCGREEN" in orchestrator.engine.pipelines


def test_orchestrator_filters_candidates_with_rule_evaluator():
    resolver = FakeResolver({"GOODIPO": "1111", "BADIPO": "2222"})
    orchestrator = IPOListingDayOrchestrator(instrument_resolver=resolver)

    evaluator = Mock()
    evaluator.evaluate = Mock(side_effect=lambda ipo: {"passed": ipo["symbol"] == "GOODIPO"})

    candidates = [
        {"symbol": "GOODIPO"},
        {"symbol": "BADIPO"},
    ]

    symbols = orchestrator.prepare_session(candidates, rule_evaluator=evaluator)

    assert symbols == ["GOODIPO"]
    assert "BADIPO" not in orchestrator.engine.pipelines


def test_orchestrator_enforces_10am_listing_start():
    """Ticks before 10:00 AM IST (during pre-open call auction) must be ignored."""
    resolver = FakeResolver({"TESTIPO": "9999"})
    session = MarketSessionService.for_ipo_listing(listing_open=time(10, 0))
    orchestrator = IPOListingDayOrchestrator(
        instrument_resolver=resolver,
        session_service=session,
    )

    orchestrator.prepare_session([{"symbol": "TESTIPO"}])
    orchestrator.start()

    # Tick during pre-open at 09:30 AM IST
    pre_open_tick = {
        "token": "9999",
        "timestamp": datetime(2026, 8, 24, 9, 30, 0),
        "price": 100.0,
        "volume": 500,
    }
    orchestrator.process_tick(pre_open_tick)

    # Tick at 10:01 AM IST (after listing open)
    market_tick = {
        "token": "9999",
        "timestamp": datetime(2026, 8, 24, 10, 1, 0),
        "price": 102.0,
        "volume": 1000,
    }
    orchestrator.process_tick(market_tick)

    report = orchestrator.generate_session_report()
    # Only the 10:01 AM tick should have been processed by the engine
    assert report["total_ticks_processed"] == 1


def test_orchestrator_full_day_tick_sequence_and_eod_report():
    resolver = FakeResolver({"ALPHAIPO": "5555"})
    session = MarketSessionService.for_ipo_listing(listing_open=time(10, 0))
    orchestrator = IPOListingDayOrchestrator(
        instrument_resolver=resolver,
        session_service=session,
        default_quantity=10,
    )

    orchestrator.prepare_session([{"symbol": "ALPHAIPO"}])
    orchestrator.start()

    # 5 observation candles (10:00 to 10:04) + pullback (10:05) + breakout (10:06, 10:07, 10:08)
    sequence = [
        (0, 100.0, 1000),
        (1, 100.0, 1000),
        (2, 100.0, 1000),
        (3, 100.0, 1000),
        (4, 100.0, 1000),
        (5, 98.0, 1000),
        (6, 101.0, 1600),
        (7, 101.2, 1000),
        (8, 101.2, 1000),
    ]

    for minute, price, volume in sequence:
        orchestrator.process_tick({
            "token": "5555",
            "timestamp": datetime(2026, 8, 24, 10, minute),
            "price": price,
            "volume": volume,
        })

    # Close session at EOD (15:30)
    orchestrator.close_eod(datetime(2026, 8, 24, 15, 30))

    report = orchestrator.generate_session_report()

    assert report["status"] == "CLOSED"
    assert report["registered_symbols"] == ["ALPHAIPO"]
    assert report["total_ticks_processed"] == len(sequence)
    assert report["total_orders"] >= 1
    assert "ALPHAIPO" in report["ipo_breakdown"]
    assert report["ipo_breakdown"]["ALPHAIPO"]["orders_count"] >= 1
