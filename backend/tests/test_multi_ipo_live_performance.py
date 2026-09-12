from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.live_paper_trading_service import LivePaperTradingService
from backend.services.ipo_live_paper_execution_service import IPOLivePaperExecutionService
from backend.services.multi_ipo_live_monitor import MultiIPOLiveMonitor
from backend.services.multi_ipo_live_performance import MultiIPOLivePerformance


class FakeController:
    def __init__(self):
        broker = PaperBroker()
        executor = StrategyExecutor(broker)

        self.paper_service = LivePaperTradingService(
            executor
        )

        self.execution_service = IPOLivePaperExecutionService(
            self.paper_service
        )

    def process_candle(self, candle):
        return {
            "action": "HOLD",
            "symbol": candle["symbol"],
            "price": candle["close"],
        }

    def reset(self):
        self.execution_service.reset()


def buy_and_sell(
    controller,
    symbol,
    entry,
    exit,
    quantity=10,
):
    controller.execution_service.execute_decision(
        {
            "action": "BUY",
            "symbol": symbol,
            "quantity": quantity,
            "price": entry,
        }
    )

    controller.execution_service.execute_decision(
        {
            "action": "EXIT",
            "symbol": symbol,
            "quantity": quantity,
            "price": exit,
        }
    )


def test_single_ipo_report():
    monitor = MultiIPOLiveMonitor()
    controller = FakeController()

    monitor.register(
        "IPOONE",
        controller,
    )

    buy_and_sell(
        controller,
        "IPOONE",
        100,
        110,
    )

    performance = MultiIPOLivePerformance(
        monitor
    )

    report = performance.get_symbol_report(
        "IPOONE"
    )

    assert report["total_trades"] == 1
    assert report["winning_trades"] == 1
    assert report["profit_loss"] == 100
    assert report["profit_loss_percent"] == 10


def test_multiple_ipo_report():
    monitor = MultiIPOLiveMonitor()

    first = FakeController()
    second = FakeController()

    monitor.register(
        "IPOONE",
        first,
    )

    monitor.register(
        "IPOTWO",
        second,
    )

    buy_and_sell(
        first,
        "IPOONE",
        100,
        110,
    )

    buy_and_sell(
        second,
        "IPOTWO",
        200,
        190,
    )

    performance = MultiIPOLivePerformance(
        monitor
    )

    report = performance.get_report()

    assert report["total_trades"] == 2
    assert report["winning_trades"] == 1
    assert report["losing_trades"] == 1

    assert report["profit_loss"] == 0

    assert (
        report["symbols"]["IPOONE"]["profit_loss"]
        == 100
    )

    assert (
        report["symbols"]["IPOTWO"]["profit_loss"]
        == -100
    )


def test_report_has_win_rate():
    monitor = MultiIPOLiveMonitor()
    controller = FakeController()

    monitor.register(
        "IPOONE",
        controller,
    )

    buy_and_sell(
        controller,
        "IPOONE",
        100,
        110,
    )

    performance = MultiIPOLivePerformance(
        monitor
    )

    report = performance.get_report()

    assert report["win_rate"] == 100


def test_empty_report():
    monitor = MultiIPOLiveMonitor()

    performance = MultiIPOLivePerformance(
        monitor
    )

    report = performance.get_report()

    assert report["total_trades"] == 0
    assert report["winning_trades"] == 0
    assert report["losing_trades"] == 0
    assert report["profit_loss"] == 0
    assert report["win_rate"] == 0


def test_unregistered_ipo_rejected():
    monitor = MultiIPOLiveMonitor()

    performance = MultiIPOLivePerformance(
        monitor
    )

    try:
        performance.get_symbol_report(
            "UNKNOWN"
        )
        assert False
    except KeyError:
        assert True


def test_reset_resets_execution_state():
    monitor = MultiIPOLiveMonitor()
    controller = FakeController()

    monitor.register(
        "IPOONE",
        controller,
    )

    buy_and_sell(
        controller,
        "IPOONE",
        100,
        110,
    )

    performance = MultiIPOLivePerformance(
        monitor
    )

    assert (
        performance.get_report()["total_trades"]
        == 1
    )

    performance.reset()

    assert (
        performance.get_report()["total_trades"]
        == 0
    )