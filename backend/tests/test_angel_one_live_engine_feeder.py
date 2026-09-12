from datetime import datetime
from unittest.mock import Mock

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.angel_one_live_engine_feeder import (
    AngelOneLiveEngineFeeder,
)
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


def make_pipeline(symbol: str = "HORIZONIND") -> tuple[IPOLivePaperPipeline, PaperBroker]:
    broker = PaperBroker()
    executor = StrategyExecutor(broker)
    paper_service = LivePaperTradingService(executor)
    execution_service = IPOLivePaperExecutionService(paper_service)
    strategy = IPOLiveListingStrategyController(
        symbol=symbol,
        quantity=10,
    )
    pipeline = IPOLivePaperPipeline(
        strategy_controller=strategy,
        execution_service=execution_service,
    )
    return pipeline, broker


def test_feeder_initialization_validation():
    pipeline, _ = make_pipeline()
    engine = LiveIPOPaperEngine(pipelines={"HORIZONIND": pipeline})

    with pytest.raises(TypeError, match="engine must be an instance"):
        AngelOneLiveEngineFeeder(engine=None, token_to_symbol={"2885": "RELIANCE"})  # type: ignore

    with pytest.raises(TypeError, match="token_to_symbol must be a dictionary"):
        AngelOneLiveEngineFeeder(engine=engine, token_to_symbol="invalid")  # type: ignore


def test_feeder_maps_token_and_forwards_tick():
    pipeline, _ = make_pipeline("HORIZONIND")
    engine = LiveIPOPaperEngine(pipelines={"HORIZONIND": pipeline})
    engine.start()

    feeder = AngelOneLiveEngineFeeder(
        engine=engine,
        token_to_symbol={"9999": "HORIZONIND"},
    )

    tick = {
        "token": "9999",
        "timestamp": datetime(2026, 8, 24, 10, 0, 15),
        "price": 100.5,
        "volume": 500,
    }

    feeder.on_tick(tick)

    stats = feeder.get_stats()
    assert stats["ticks_received"] == 1
    assert stats["ticks_forwarded"] == 1
    assert stats["ticks_dropped"] == 0
    assert engine.ticks_processed == 1


def test_feeder_drops_unmapped_token():
    pipeline, _ = make_pipeline("HORIZONIND")
    engine = LiveIPOPaperEngine(pipelines={"HORIZONIND": pipeline})
    engine.start()

    feeder = AngelOneLiveEngineFeeder(
        engine=engine,
        token_to_symbol={"9999": "HORIZONIND"},
    )

    unmapped_tick = {
        "token": "1234",
        "timestamp": datetime(2026, 8, 24, 10, 0, 15),
        "price": 100.5,
        "volume": 500,
    }

    feeder.on_tick(unmapped_tick)

    stats = feeder.get_stats()
    assert stats["ticks_received"] == 1
    assert stats["ticks_forwarded"] == 0
    assert stats["ticks_dropped"] == 1
    assert engine.ticks_processed == 0


def test_feeder_drops_malformed_ticks():
    pipeline, _ = make_pipeline("HORIZONIND")
    engine = LiveIPOPaperEngine(pipelines={"HORIZONIND": pipeline})
    engine.start()

    feeder = AngelOneLiveEngineFeeder(
        engine=engine,
        token_to_symbol={"9999": "HORIZONIND"},
    )

    # Missing/invalid timestamp
    feeder.on_tick({"token": "9999", "timestamp": "invalid", "price": 100.0})
    # Non-positive price
    feeder.on_tick({"token": "9999", "timestamp": datetime(2026, 8, 24, 10, 0, 0), "price": -5.0})
    # Non-dict tick
    feeder.on_tick("not_a_dict")  # type: ignore

    stats = feeder.get_stats()
    assert stats["ticks_received"] == 3
    assert stats["ticks_dropped"] == 3
    assert stats["ticks_forwarded"] == 0


def test_feeder_symbol_fallback():
    pipeline, _ = make_pipeline("HORIZONIND")
    engine = LiveIPOPaperEngine(pipelines={"HORIZONIND": pipeline})
    engine.start()

    # Empty token_to_symbol map, but tick contains valid symbol
    feeder = AngelOneLiveEngineFeeder(
        engine=engine,
        token_to_symbol={},
    )

    tick = {
        "token": "unknown",
        "symbol": "HORIZONIND",
        "timestamp": datetime(2026, 8, 24, 10, 0, 15),
        "price": 105.0,
        "volume": 200,
    }

    feeder.on_tick(tick)

    stats = feeder.get_stats()
    assert stats["ticks_forwarded"] == 1


def test_feeder_start_and_stop_lifecycle():
    pipeline, _ = make_pipeline("HORIZONIND")
    engine = LiveIPOPaperEngine(pipelines={"HORIZONIND": pipeline})

    mock_ws = Mock()
    mock_ws.connect = Mock()
    mock_ws.close = Mock()

    feeder = AngelOneLiveEngineFeeder(
        engine=engine,
        token_to_symbol={"9999": "HORIZONIND"},
        ws_source=mock_ws,
    )

    feeder.start()
    assert engine.running is True
    mock_ws.connect.assert_called_once()

    feeder.stop()
    assert engine.running is False
    mock_ws.close.assert_called_once()


def test_feeder_end_to_end_paper_order_execution():
    """
    Test complete flow:
    Tick from Angel One WS format -> Feeder -> Engine -> Candle Completed -> Strategy BUY -> Paper Order
    """
    pipeline, broker = make_pipeline("HORIZONIND")
    engine = LiveIPOPaperEngine(pipelines={"HORIZONIND": pipeline})

    feeder = AngelOneLiveEngineFeeder(
        engine=engine,
        token_to_symbol={"7777": "HORIZONIND"},
    )
    feeder.start()

    sequence = [
        (15, 100.0, 1000),
        (16, 100.0, 1000),
        (17, 100.0, 1000),
        (18, 100.0, 1000),
        (19, 100.0, 1000),
        (20, 98.0, 1000),
        (21, 101.0, 1600),
        (22, 101.2, 1000),
        (23, 101.2, 1000),
    ]

    for minute, price, volume in sequence:
        feeder.on_tick({
            "token": "7777",
            "timestamp": datetime(2026, 8, 31, 9, minute),
            "price": price,
            "volume": volume,
        })

    orders = engine.get_orders()
    assert len(orders) == 1
    assert orders[0]["symbol"] == "HORIZONIND"
    assert orders[0]["action"] == "BUY"
    assert orders[0]["quantity"] == 10

    positions = engine.get_positions()
    assert positions["HORIZONIND"] is not None
    assert positions["HORIZONIND"]["symbol"] == "HORIZONIND"
