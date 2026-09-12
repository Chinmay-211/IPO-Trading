from datetime import datetime, time

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_live_listing_strategy_controller import (
    IPOLiveListingStrategyController,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)
from backend.services.ipo_live_paper_pipeline import (
    IPOLivePaperPipeline,
)
from backend.services.live_ipo_paper_engine import (
    LiveIPOPaperEngine,
)
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)
from backend.services.market_session_service import (
    MarketSessionService,
)


# ============================================================
# TEST FACTORIES
# ============================================================


def make_pipeline(
    symbol: str = "TESTIPO",
) -> IPOLivePaperPipeline:
    """
    Create a complete paper-trading pipeline.

    Flow:

        Strategy
            ↓
        Paper Execution Service
            ↓
        Live Paper Trading Service
            ↓
        Strategy Executor
            ↓
        Paper Broker
    """

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

    strategy = IPOLiveListingStrategyController(
        symbol=symbol,
        quantity=10,
    )

    return IPOLivePaperPipeline(
        strategy_controller=strategy,
        execution_service=execution_service,
    )


def make_session_service() -> MarketSessionService:
    """
    Create the NSE regular-session configuration
    used by these tests.
    """

    return MarketSessionService(
        market_open=time(
            9,
            15,
        ),
        market_close=time(
            15,
            30,
        ),
    )


def make_engine() -> LiveIPOPaperEngine:
    """
    Create a complete session-aware live IPO
    paper-trading engine.
    """

    pipeline = make_pipeline(
        symbol="TESTIPO"
    )

    return LiveIPOPaperEngine(
        pipelines={
            "TESTIPO": pipeline,
        },
        session_service=make_session_service(),
    )


# ============================================================
# TICK FACTORY
# ============================================================


def tick(
    minute: int,
    price: float,
    volume: int = 1000,
) -> dict:
    """
    Create one simulated live market tick.

    Test date:
        31 August 2026

    Market time:
        09:15 onwards
    """

    return {
        "symbol": "TESTIPO",
        "timestamp": datetime(
            2026,
            8,
            31,
            9,
            minute,
        ),
        "price": price,
        "volume": volume,
    }


# ============================================================
# LIFECYCLE TESTS
# ============================================================


def test_engine_starts_in_stopped_state():
    engine = make_engine()

    state = engine.get_state()

    assert state["running"] is False
    assert state["session_closed"] is False

    assert state["ticks_processed"] == 0
    assert state["candles_completed"] == 0
    assert state["decisions_processed"] == 0


def test_engine_does_not_process_ticks_before_start():
    engine = make_engine()

    result = engine.process_tick(
        tick(
            15,
            100,
        )
    )

    assert result is None

    state = engine.get_state()

    assert state["running"] is False
    assert state["ticks_processed"] == 0


def test_engine_start():
    engine = make_engine()

    engine.start()

    state = engine.get_state()

    assert state["running"] is True
    assert state["session_closed"] is False


def test_engine_stop():
    engine = make_engine()

    engine.start()

    engine.stop()

    state = engine.get_state()

    assert state["running"] is False


# ============================================================
# MARKET SESSION TESTS
# ============================================================


def test_pre_open_tick_is_ignored():
    engine = make_engine()

    engine.start()

    result = engine.process_tick(
        {
            "symbol": "TESTIPO",
            "timestamp": datetime(
                2026,
                8,
                31,
                9,
                0,
            ),
            "price": 100,
            "volume": 1000,
        }
    )

    assert result is None

    state = engine.get_state()

    assert state["ticks_processed"] == 0
    assert state["candles_completed"] == 0


def test_market_open_tick_is_accepted():
    engine = make_engine()

    engine.start()

    result = engine.process_tick(
        tick(
            15,
            100,
        )
    )

    assert result is None

    state = engine.get_state()

    assert state["ticks_processed"] == 1


def test_market_close_tick_is_ignored():
    engine = make_engine()

    engine.start()

    result = engine.process_tick(
        {
            "symbol": "TESTIPO",
            "timestamp": datetime(
                2026,
                8,
                31,
                15,
                30,
            ),
            "price": 100,
            "volume": 1000,
        }
    )

    assert result is None

    state = engine.get_state()

    assert state["ticks_processed"] == 0


def test_after_market_close_tick_is_ignored():
    engine = make_engine()

    engine.start()

    result = engine.process_tick(
        {
            "symbol": "TESTIPO",
            "timestamp": datetime(
                2026,
                8,
                31,
                15,
                31,
            ),
            "price": 100,
            "volume": 1000,
        }
    )

    assert result is None

    state = engine.get_state()

    assert state["ticks_processed"] == 0


def test_session_state_before_open():
    engine = make_engine()

    state = engine.get_session_state(
        datetime(
            2026,
            8,
            31,
            9,
            0,
        )
    )

    assert state == "PRE_OPEN"


def test_session_state_during_market():
    engine = make_engine()

    state = engine.get_session_state(
        datetime(
            2026,
            8,
            31,
            10,
            0,
        )
    )

    assert state == "OPEN"


def test_session_state_after_close():
    engine = make_engine()

    state = engine.get_session_state(
        datetime(
            2026,
            8,
            31,
            15,
            30,
        )
    )

    assert state == "CLOSED"


# ============================================================
# CANDLE BUILDING TESTS
# ============================================================


def test_first_tick_starts_candle():
    engine = make_engine()

    engine.start()

    result = engine.process_tick(
        tick(
            15,
            100,
        )
    )

    assert result is None

    state = engine.get_state()

    assert state["ticks_processed"] == 1
    assert state["candles_completed"] == 0


def test_same_minute_ticks_do_not_complete_candle():
    engine = make_engine()

    engine.start()

    engine.process_tick(
        tick(
            15,
            100,
        )
    )

    engine.process_tick(
        tick(
            15,
            102,
        )
    )

    state = engine.get_state()

    assert state["ticks_processed"] == 2
    assert state["candles_completed"] == 0


def test_new_minute_completes_previous_candle():
    engine = make_engine()

    engine.start()

    engine.process_tick(
        tick(
            15,
            100,
        )
    )

    engine.process_tick(
        tick(
            15,
            102,
        )
    )

    result = engine.process_tick(
        tick(
            16,
            101,
        )
    )

    assert result is None

    state = engine.get_state()

    assert state["ticks_processed"] == 3
    assert state["candles_completed"] == 1


def test_engine_flush_completes_active_candle():
    engine = make_engine()

    engine.start()

    engine.process_tick(
        tick(
            15,
            100,
        )
    )

    state_before = engine.get_state()

    assert state_before["candles_completed"] == 0

    result = engine.flush()

    assert "TESTIPO" in result

    state_after = engine.get_state()

    assert state_after["candles_completed"] == 1


# ============================================================
# STRATEGY + PAPER EXECUTION TEST
# ============================================================


def test_live_ticks_generate_buy_and_execute_paper_order():
    engine = make_engine()

    engine.start()

    sequence = [
        (15, 100, 1000),
        (16, 100, 1000),
        (17, 100, 1000),
        (18, 100, 1000),
        (19, 100, 1000),
        (20, 98.0, 1000),
        (21, 101, 1600),
        (22, 101.2, 1000),
        (23, 101.2, 1000),
    ]

    results = []

    for minute, price, volume in sequence:
        result = engine.process_tick(
            tick(
                minute,
                price,
                volume,
            )
        )

        if result is not None:
            results.append(result)

    assert len(results) == 1

    result = results[0]

    assert (
        result["decision"]["action"]
        == "BUY"
    )

    assert (
        result["execution"]["action"]
        == "BUY"
    )

    assert (
        result["execution"]["executed"]
        is True
    )

    position = engine.get_positions()[
        "TESTIPO"
    ]

    assert position is not None

    assert position["symbol"] == "TESTIPO"


def test_buy_order_is_available_from_engine():
    engine = make_engine()

    engine.start()

    sequence = [
        (15, 100, 1000),
        (16, 100, 1000),
        (17, 100, 1000),
        (18, 100, 1000),
        (19, 100, 1000),
        (20, 98.0, 1000),
        (21, 101, 1600),
        (22, 101.2, 1000),
        (23, 101.2, 1000),
    ]

    for minute, price, volume in sequence:
        engine.process_tick(
            tick(
                minute,
                price,
                volume,
            )
        )

    orders = engine.get_orders()

    assert len(orders) == 1

    assert orders[0]["action"] == "BUY"


# ============================================================
# POSITION TESTS
# ============================================================


def test_engine_position_is_none_before_entry():
    engine = make_engine()

    engine.start()

    positions = engine.get_positions()

    assert positions["TESTIPO"] is None


def test_engine_position_exists_after_buy():
    engine = make_engine()

    engine.start()

    sequence = [
        (15, 100, 1000),
        (16, 100, 1000),
        (17, 100, 1000),
        (18, 100, 1000),
        (19, 100, 1000),
        (20, 98.0, 1000),
        (21, 101, 1600),
        (22, 101.2, 1000),
        (23, 101.2, 1000),
    ]

    for minute, price, volume in sequence:
        engine.process_tick(
            tick(
                minute,
                price,
                volume,
            )
        )

    position = engine.get_positions()[
        "TESTIPO"
    ]

    assert position is not None
    assert position["quantity"] == 10


# ============================================================
# ERROR HANDLING
# ============================================================


def test_unknown_ipo_symbol_is_rejected():
    engine = make_engine()

    engine.start()

    with pytest.raises(KeyError):
        engine.process_tick(
            {
                "symbol": "UNKNOWN",
                "timestamp": datetime(
                    2026,
                    8,
                    31,
                    10,
                    0,
                ),
                "price": 100,
                "volume": 1000,
            }
        )


def test_missing_tick_symbol_is_rejected():
    engine = make_engine()

    engine.start()

    with pytest.raises(ValueError):
        engine.process_tick(
            {
                "timestamp": datetime(
                    2026,
                    8,
                    31,
                    10,
                    0,
                ),
                "price": 100,
                "volume": 1000,
            }
        )


def test_missing_tick_timestamp_is_rejected():
    engine = make_engine()

    engine.start()

    with pytest.raises(TypeError):
        engine.process_tick(
            {
                "symbol": "TESTIPO",
                "price": 100,
                "volume": 1000,
            }
        )


def test_missing_tick_price_is_rejected():
    engine = make_engine()

    engine.start()

    with pytest.raises(ValueError):
        engine.process_tick(
            {
                "symbol": "TESTIPO",
                "timestamp": datetime(
                    2026,
                    8,
                    31,
                    10,
                    0,
                ),
                "volume": 1000,
            }
        )


def test_invalid_tick_price_is_rejected():
    engine = make_engine()

    engine.start()

    with pytest.raises(ValueError):
        engine.process_tick(
            {
                "symbol": "TESTIPO",
                "timestamp": datetime(
                    2026,
                    8,
                    31,
                    10,
                    0,
                ),
                "price": 0,
                "volume": 1000,
            }
        )


def test_missing_tick_volume_is_rejected():
    engine = make_engine()

    engine.start()

    with pytest.raises(ValueError):
        engine.process_tick(
            {
                "symbol": "TESTIPO",
                "timestamp": datetime(
                    2026,
                    8,
                    31,
                    10,
                    0,
                ),
                "price": 100,
            }
        )


# ============================================================
# SESSION CLOSE
# ============================================================


def test_close_session_stops_engine():
    engine = make_engine()

    engine.start()

    result = engine.close_session(
        datetime(
            2026,
            8,
            31,
            15,
            30,
        )
    )

    assert (
        result["action"]
        == "SESSION_CLOSED"
    )

    state = engine.get_state()

    assert state["running"] is False
    assert state["session_closed"] is True


def test_closed_engine_rejects_new_ticks():
    engine = make_engine()

    engine.start()

    engine.close_session(
        datetime(
            2026,
            8,
            31,
            15,
            30,
        )
    )

    before = engine.get_state()[
        "ticks_processed"
    ]

    result = engine.process_tick(
        tick(
            20,
            100,
        )
    )

    assert result is None

    after = engine.get_state()[
        "ticks_processed"
    ]

    assert after == before


# ============================================================
# REPORTING
# ============================================================


def test_engine_report_initial_state():
    engine = make_engine()

    report = engine.get_report()

    assert report["running"] is False
    assert report["session_closed"] is False

    assert report["ipo_count"] == 1

    assert report["ticks_processed"] == 0
    assert report["candles_completed"] == 0
    assert report["decisions_processed"] == 0

    assert report["order_count"] == 0
    assert report["orders"] == []

    assert report["positions"][
        "TESTIPO"
    ] is None

    assert report["realized_pnl"] == 0.0


def test_engine_state_contains_ipo_state():
    engine = make_engine()

    state = engine.get_state()

    assert "ipos" in state

    assert "TESTIPO" in state[
        "ipos"
    ]


# ============================================================
# RESET
# ============================================================


def test_engine_reset():
    engine = make_engine()

    engine.start()

    engine.process_tick(
        tick(
            15,
            100,
        )
    )

    engine.reset()

    state = engine.get_state()

    assert state["running"] is False
    assert state["session_closed"] is False

    assert state["ticks_processed"] == 0
    assert state["candles_completed"] == 0
    assert state["decisions_processed"] == 0

    assert state["last_results"] == {}

    assert state["ipos"]["TESTIPO"][
        "decisions"
    ] == 0

    assert engine.get_orders() == []

    assert engine.get_realized_pnl() == 0.0

    assert engine.get_positions()[
        "TESTIPO"
    ] is None