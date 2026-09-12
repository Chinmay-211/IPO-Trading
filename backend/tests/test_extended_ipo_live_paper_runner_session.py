from datetime import datetime, time

from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.angel_one_ipo_live_paper_runner import (
    AngelOneIPOLivePaperRunner,
)
from backend.services.extended_ipo_live_paper_runner import (
    ExtendedIPOLivePaperRunner,
)
from backend.services.ipo_eod_force_exit_service import (
    IPOEODForceExitService,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)
from backend.services.market_session_service import (
    MarketSessionService,
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


def make_runner(symbol="IPOONE"):
    broker = PaperBroker()
    executor = StrategyExecutor(broker)
    paper = LivePaperTradingService(executor)
    execution = IPOLivePaperExecutionService(paper)

    runner = AngelOneIPOLivePaperRunner(
        symbol=symbol,
        quantity=10,
        exchange_type=1,
        instrument_token="111",
        execution_service=execution,
    )

    runner.websocket = FakeWebSocket()

    return runner, execution


def make_extended():
    runner, execution = make_runner()

    session = MarketSessionService(
        market_open=time(9, 15),
        market_close=time(15, 30),
    )

    eod = IPOEODForceExitService(
        execution_service=execution,
        session_service=session,
    )

    extended = ExtendedIPOLivePaperRunner(
        {"IPOONE": runner}
    )

    extended.session_service = session
    extended.eod_service = eod

    return extended, runner, execution


def candle(
    timestamp,
    price,
):
    return {
        "symbol": "IPOONE",
        "timestamp": timestamp,
        "open_price": price,
        "high_price": price,
        "low_price": price,
        "close_price": price,
        "volume": 100,
    }


def test_pre_open_candle_is_ignored():
    extended, _, _ = make_extended()

    result = extended.process_candle(
        "IPOONE",
        candle(
            datetime(2026, 8, 31, 9, 0),
            100,
        ),
    )

    assert result is None
    assert extended.candles_processed == 0


def test_open_candle_is_processed():
    extended, _, _ = make_extended()

    extended.process_candle(
        "IPOONE",
        candle(
            datetime(2026, 8, 31, 9, 15),
            100,
        ),
    )

    assert extended.candles_processed == 1


def test_after_close_candle_is_not_processed():
    extended, _, _ = make_extended()

    result = extended.process_candle(
        "IPOONE",
        candle(
            datetime(2026, 8, 31, 15, 30),
            100,
        ),
    )

    assert result is None
    assert extended.candles_processed == 0


def test_session_state_is_exposed():
    extended, _, _ = make_extended()

    state = extended.get_state()

    assert state["session"]["state"] == "CLOSED"


def test_eod_service_is_exposed():
    extended, _, _ = make_extended()

    state = extended.get_state()

    assert state["session"]["eod_session_closed"] is False


def test_reset_resets_session_services():
    extended, _, _ = make_extended()

    extended.eod_service.session_closed = True
    extended.reset()

    assert extended.eod_service.session_closed is False


def test_open_position_can_be_force_exited_at_eod():
    extended, _, execution = make_extended()

    execution.execute_decision(
        {
            "action": "BUY",
            "symbol": "IPOONE",
            "quantity": 10,
            "price": 100,
        },
        timestamp=datetime(
            2026,
            8,
            31,
            10,
            0,
        ),
    )

    result = extended.force_eod_exit(
        "IPOONE",
        105,
        datetime(
            2026,
            8,
            31,
            15,
            30,
        ),
    )

    assert result["action"] == "EOD_EXIT"
    assert result["executed"] is True
    assert result["eod_force_exit"] is True
    assert execution.get_position("IPOONE") is None


def test_eod_exit_without_position_creates_no_order():
    extended, _, _ = make_extended()

    result = extended.force_eod_exit(
        "IPOONE",
        105,
        datetime(
            2026,
            8,
            31,
            15,
            30,
        ),
    )

    assert result["action"] == "EOD_EXIT"
    assert result["executed"] is False


def test_force_eod_exit_requires_valid_symbol():
    extended, _, _ = make_extended()

    try:
        extended.force_eod_exit(
            "",
            100,
            datetime(
                2026,
                8,
                31,
                15,
                30,
            ),
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for empty symbol."
    )


def test_force_eod_exit_requires_positive_price():
    extended, _, _ = make_extended()

    try:
        extended.force_eod_exit(
            "IPOONE",
            0,
            datetime(
                2026,
                8,
                31,
                15,
                30,
            ),
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for non-positive price."
    )