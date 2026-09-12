from datetime import datetime

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.angel_one_ipo_live_paper_runner import (
    AngelOneIPOLivePaperRunner,
)
from backend.services.extended_ipo_live_paper_runner import (
    ExtendedIPOLivePaperRunner,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)


class FakeWebSocket:
    def __init__(self):
        self.connected = False
        self.subscribed = False

    def connect(self):
        self.connected = True

    def subscribe(
        self,
        correlation_id,
        exchange_type,
        tokens,
        mode=1,
    ):
        self.subscribed = True

    def close(self):
        self.connected = False
        self.subscribed = False

    def reset(self):
        self.connected = False
        self.subscribed = False

    def get_candles(self, symbol=None):
        return []


def make_runner(
    symbol="IPOONE",
    token="111",
):
    broker = PaperBroker()
    executor = StrategyExecutor(broker)
    paper = LivePaperTradingService(executor)
    execution = IPOLivePaperExecutionService(paper)

    runner = AngelOneIPOLivePaperRunner(
        symbol=symbol,
        quantity=10,
        exchange_type=1,
        instrument_token=token,
        execution_service=execution,
    )

    runner.websocket = FakeWebSocket()

    return runner


def make_extended_runner():
    first = make_runner("IPOONE", "111")
    second = make_runner("IPOTWO", "222")

    return ExtendedIPOLivePaperRunner(
        {
            "IPOONE": first,
            "IPOTWO": second,
        }
    )


def candle(
    symbol,
    minute,
    price,
):
    return {
        "symbol": symbol,
        "timestamp": datetime(
            2026,
            8,
            31,
            9,
            minute,
        ),
        "open_price": price,
        "high_price": price,
        "low_price": price,
        "close_price": price,
        "volume": 100,
    }


def test_constructor_requires_dictionary():
    with pytest.raises(TypeError):
        ExtendedIPOLivePaperRunner(None)


def test_constructor_requires_runner():
    with pytest.raises(ValueError):
        ExtendedIPOLivePaperRunner({})


def test_constructor_validates_runner_type():
    with pytest.raises(TypeError):
        ExtendedIPOLivePaperRunner(
            {"IPOONE": object()}
        )


def test_start_starts_all_runners():
    extended = make_extended_runner()

    extended.start()

    assert extended.running is True
    assert extended.started_at is not None

    assert extended.runners[
        "IPOONE"
    ].running is True

    assert extended.runners[
        "IPOTWO"
    ].running is True


def test_start_is_idempotent():
    extended = make_extended_runner()

    extended.start()
    first_started = extended.started_at

    extended.start()

    assert extended.started_at == first_started


def test_stop_stops_all_runners():
    extended = make_extended_runner()

    extended.start()
    extended.stop()

    assert extended.running is False
    assert extended.stopped_at is not None

    assert extended.runners[
        "IPOONE"
    ].running is False

    assert extended.runners[
        "IPOTWO"
    ].running is False


def test_process_candle_updates_state():
    extended = make_extended_runner()

    result = extended.process_candle(
        "IPOONE",
        candle(
            "IPOONE",
            30,
            100,
        ),
    )

    assert result is None
    assert extended.candles_processed == 1


def test_process_candle_rejects_unknown_symbol():
    extended = make_extended_runner()

    with pytest.raises(KeyError):
        extended.process_candle(
            "UNKNOWN",
            candle(
                "UNKNOWN",
                30,
                100,
            ),
        )


def test_process_candle_rejects_empty_symbol():
    extended = make_extended_runner()

    with pytest.raises(ValueError):
        extended.process_candle(
            "",
            candle(
                "IPOONE",
                30,
                100,
            ),
        )


def test_flush_returns_all_symbols():
    extended = make_extended_runner()

    results = extended.flush()

    assert set(results.keys()) == {
        "IPOONE",
        "IPOTWO",
    }


def test_orders_initially_empty():
    extended = make_extended_runner()

    assert extended.get_orders() == []


def test_positions_initially_empty():
    extended = make_extended_runner()

    positions = extended.get_positions()

    assert positions["IPOONE"] is None
    assert positions["IPOTWO"] is None


def test_realized_pnl_initially_zero():
    extended = make_extended_runner()

    assert extended.get_realized_pnl() == 0.0


def test_report_contains_session_information():
    extended = make_extended_runner()

    report = extended.get_report()

    assert report["running"] is False
    assert report["ipo_count"] == 2
    assert report["candles_processed"] == 0
    assert report["decisions_processed"] == 0
    assert report["order_count"] == 0
    assert report["realized_pnl"] == 0.0


def test_state_contains_each_ipo():
    extended = make_extended_runner()

    state = extended.get_state()

    assert state["running"] is False
    assert set(state["ipos"].keys()) == {
        "IPOONE",
        "IPOTWO",
    }


def test_reset_clears_session():
    extended = make_extended_runner()

    extended.start()

    extended.process_candle(
        "IPOONE",
        candle(
            "IPOONE",
            30,
            100,
        ),
    )

    extended.reset()

    state = extended.get_state()

    assert state["running"] is False
    assert state["started_at"] is None
    assert state["stopped_at"] is None
    assert state["candles_processed"] == 0
    assert state["decisions_processed"] == 0


def test_reset_clears_runner_state():
    extended = make_extended_runner()

    extended.process_candle(
        "IPOONE",
        candle(
            "IPOONE",
            30,
            100,
        ),
    )

    extended.reset()

    assert (
        extended.runners["IPOONE"].last_candle
        is None
    )

    assert (
        extended.runners["IPOONE"].last_result
        is None
    )


def test_symbol_names_are_normalized():
    runner = make_runner("ipoone", "111")

    extended = ExtendedIPOLivePaperRunner(
        {"ipoone": runner}
    )

    assert "IPOONE" in extended.runners