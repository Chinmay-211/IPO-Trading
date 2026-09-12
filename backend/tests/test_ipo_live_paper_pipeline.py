from datetime import datetime

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
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


def candle(
    minute,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
):
    return {
        "symbol": "TESTIPO",
        "timestamp": datetime(
            2026,
            8,
            31,
            9,
            minute,
        ),
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "close_price": close_price,
        "volume": volume,
    }


def make_pipeline():
    broker = PaperBroker()
    executor = StrategyExecutor(broker)

    paper_service = LivePaperTradingService(
        executor
    )

    execution_service = (
        IPOLivePaperExecutionService(
            paper_service
        )
    )

    strategy = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    return IPOLivePaperPipeline(
        strategy_controller=strategy,
        execution_service=execution_service,
    )


def entry_sequence():
    return [
        candle(15, 100, 101, 99.5, 100, 1000),
        candle(16, 100, 101, 99.5, 100, 1000),
        candle(17, 100, 101, 99.5, 100, 1000),
        candle(18, 100, 101, 99.5, 100, 1000),
        candle(19, 100, 101, 99.5, 100, 1000),
        candle(20, 99, 99.5, 98, 98.5, 1000),
        candle(21, 100, 102, 99.8, 101, 1600),
        candle(22, 101, 101.5, 100.8, 101.2, 1000),
    ]


def test_pipeline_generates_buy_and_executes():
    pipeline = make_pipeline()

    results = pipeline.process_candles(
        entry_sequence()
    )

    assert len(results) == 1

    result = results[0]

    assert result["decision"]["action"] == "BUY"
    assert result["execution"]["action"] == "BUY"
    assert result["execution"]["executed"] is True

    position = pipeline.get_position()

    assert position is not None
    assert position["symbol"] == "TESTIPO"


def test_pipeline_executes_target_exit():
    pipeline = make_pipeline()

    pipeline.process_candles(
        entry_sequence()
    )

    target = pipeline.get_state()[
        "strategy"
    ]["target_price"]

    result = pipeline.process_candle(
        candle(
            23,
            101,
            target + 1,
            100.5,
            target,
            1000,
        )
    )

    assert result is not None

    assert result["decision"]["action"] == "SELL"
    assert result["decision"]["outcome"] == "TARGET"

    assert result["execution"]["action"] == "SELL"
    assert result["execution"]["executed"] is True

    assert pipeline.get_position() is None


def test_pipeline_executes_stop_loss():
    pipeline = make_pipeline()

    pipeline.process_candles(
        entry_sequence()
    )

    state = pipeline.get_state()["strategy"]

    stop = state["stop_loss_price"]

    result = pipeline.process_candle(
        candle(
            23,
            101,
            101.5,
            stop - 1,
            stop,
            1000,
        )
    )

    assert result is not None

    assert result["decision"]["action"] == "SELL"
    assert result["decision"]["outcome"] == "STOP_LOSS"

    assert result["execution"]["action"] == "SELL"
    assert result["execution"]["executed"] is True

    assert pipeline.get_position() is None


def test_pipeline_does_not_execute_without_decision():
    pipeline = make_pipeline()

    result = pipeline.process_candle(
        candle(
            15,
            100,
            101,
            99,
            100,
            1000,
        )
    )

    assert result is None
    assert pipeline.get_orders() == []


def test_pipeline_reset():
    pipeline = make_pipeline()

    pipeline.process_candles(
        entry_sequence()
    )

    assert len(pipeline.decisions) == 1

    pipeline.reset()

    state = pipeline.get_state()

    assert state["decisions"] == 0
    assert state["executions"] == 0
    assert state["strategy"]["candles"] == 0
    assert state["strategy"]["position_open"] is False
    assert pipeline.get_orders() == []
    assert pipeline.get_realized_pnl() == 0.0