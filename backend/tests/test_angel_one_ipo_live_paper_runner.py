from datetime import datetime
from unittest.mock import MagicMock

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)
from backend.services.angel_one_ipo_live_paper_runner import (
    AngelOneIPOLivePaperRunner,
)


def make_runner(
    screening_passed=True,
):
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

    runner = AngelOneIPOLivePaperRunner(
        symbol="TESTIPO",
        quantity=10,
        exchange_type=1,
        instrument_token="12345",
        execution_service=execution_service,
        screening_passed=screening_passed,
    )

    return runner


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


def entry_sequence():
    return [
        candle(
            15,
            100,
            101,
            99.5,
            100,
            1000,
        ),
        candle(
            16,
            100,
            101,
            99.5,
            100,
            1000,
        ),
        candle(
            17,
            100,
            101,
            99.5,
            100,
            1000,
        ),
        candle(
            18,
            100,
            101,
            99.5,
            100,
            1000,
        ),
        candle(
            19,
            100,
            101,
            99.5,
            100,
            1000,
        ),
        candle(
            20,
            99,
            99.5,
            98,
            98.5,
            1000,
        ),
        candle(
            21,
            100,
            102,
            99.8,
            101,
            1600,
        ),
        candle(
            22,
            101,
            101.5,
            100.8,
            101.2,
            1000,
        ),
    ]


def test_runner_initializes():
    runner = make_runner()

    assert runner.symbol == "TESTIPO"
    assert runner.quantity == 10
    assert runner.instrument_token == "12345"
    assert runner.running is False


def test_runner_candle_reaches_pipeline():
    runner = make_runner()

    for item in entry_sequence():
        runner._on_candle(item)

    assert runner.last_candle is not None

    assert (
        runner.last_candle["symbol"]
        == "TESTIPO"
    )

    assert runner.last_result is not None

    assert (
        runner.last_result["decision"]["action"]
        == "BUY"
    )


def test_runner_buy_reaches_paper_broker():
    runner = make_runner()

    for item in entry_sequence():
        runner._on_candle(item)

    orders = runner.get_orders()

    assert len(orders) == 1

    assert (
        orders[0]["side"]
        == "BUY"
    )

    position = runner.get_position()

    assert position is not None

    assert (
        position["symbol"]
        == "TESTIPO"
    )


def test_runner_target_reaches_paper_broker():
    runner = make_runner()

    for item in entry_sequence():
        runner._on_candle(item)

    assert runner.last_result is not None

    decision = runner.last_result[
        "decision"
    ]

    assert (
        decision["action"]
        == "BUY"
    )

    target = decision.get(
        "target_price"
    )

    assert target is not None

    runner._on_candle(
        candle(
            23,
            target,
            target + 1,
            target,
            target,
            1000,
        )
    )

    orders = runner.get_orders()

    assert len(orders) == 2

    assert (
        orders[0]["side"]
        == "BUY"
    )

    assert (
        orders[1]["side"]
        == "SELL"
    )

    assert (
        runner.get_position()
        is None
    )


def test_runner_screening_failure_does_not_trade():
    runner = make_runner(
        screening_passed=False
    )

    runner._on_candle(
        candle(
            15,
            100,
            101,
            99,
            100,
            1000,
        )
    )

    assert runner.last_result is not None

    assert (
        runner.last_result[
            "decision"
        ]["action"]
        == "NO_TRADE"
    )

    assert runner.get_orders() == []


def test_runner_close_does_not_place_order_when_not_connected():
    runner = make_runner()

    runner.stop()

    assert runner.running is False


def test_runner_reset_clears_state():
    runner = make_runner()

    for item in entry_sequence():
        runner._on_candle(item)

    assert runner.last_result is not None

    runner.reset()

    state = runner.get_state()

    assert (
        state["running"]
        is False
    )

    assert (
        state["last_candle"]
        is None
    )

    assert (
        state["last_result"]
        is None
    )

    assert runner.get_orders() == []

    assert (
        runner.get_position()
        is None
    )

    assert (
        runner.get_realized_pnl()
        == 0
    )


def test_websocket_candle_callback_is_connected():
    runner = make_runner()

    assert (
        runner.websocket.on_candle
        == runner._on_candle
    )


def test_start_subscribes_to_configured_token():
    runner = make_runner()

    runner.websocket.connect = (
        MagicMock()
    )

    runner.websocket.subscribe = (
        MagicMock()
    )

    runner.start()

    runner.websocket.connect.assert_called_once()

    runner.websocket.subscribe.assert_called_once_with(
        correlation_id=(
            "IPO_PAPER_12345"
        ),
        exchange_type=1,
        tokens=["12345"],
        mode=1,
    )

    assert runner.running is True