from datetime import datetime


from backend.services.multi_ipo_live_monitor import (
    MultiIPOLiveMonitor,
)


class FakeController:
    def __init__(self):
        self.candles = []

    def process_candle(self, candle):
        self.candles.append(candle)

        return {
            "action": "HOLD",
            "symbol": candle["symbol"],
            "price": candle["close"],
        }


def candle(
    symbol,
    price,
):
    return {
        "symbol": symbol,
        "timestamp": datetime(
            2026,
            8,
            31,
            10,
            0,
        ),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 100,
        "interval": "1m",
    }


def test_register_single_ipo():
    monitor = MultiIPOLiveMonitor()

    controller = FakeController()

    monitor.register(
        "IPOONE",
        controller,
    )

    assert monitor.count() == 1
    assert monitor.contains("IPOONE")
    assert monitor.symbols() == ["IPOONE"]


def test_register_multiple_ipos():
    monitor = MultiIPOLiveMonitor()

    monitor.register(
        "IPOONE",
        FakeController(),
    )

    monitor.register(
        "IPOTWO",
        FakeController(),
    )

    assert monitor.count() == 2
    assert set(monitor.symbols()) == {
        "IPOONE",
        "IPOTWO",
    }


def test_duplicate_registration_rejected():
    monitor = MultiIPOLiveMonitor()

    monitor.register(
        "IPOONE",
        FakeController(),
    )

    try:
        monitor.register(
            "IPOONE",
            FakeController(),
        )
        assert False
    except ValueError:
        assert True


def test_candle_goes_to_correct_ipo():
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

    monitor.process_candle(
        "IPOONE",
        candle("IPOONE", 100),
    )

    assert len(first.candles) == 1
    assert len(second.candles) == 0


def test_multiple_ipos_are_isolated():
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

    monitor.process_candle(
        "IPOONE",
        candle("IPOONE", 100),
    )

    monitor.process_candle(
        "IPOTWO",
        candle("IPOTWO", 200),
    )

    assert len(first.candles) == 1
    assert len(second.candles) == 1

    assert first.candles[0]["close"] == 100
    assert second.candles[0]["close"] == 200


def test_result_is_returned():
    monitor = MultiIPOLiveMonitor()

    monitor.register(
        "IPOONE",
        FakeController(),
    )

    result = monitor.process_candle(
        "IPOONE",
        candle("IPOONE", 125),
    )

    assert result["action"] == "HOLD"
    assert result["price"] == 125


def test_state_contains_latest_candle_and_result():
    monitor = MultiIPOLiveMonitor()

    monitor.register(
        "IPOONE",
        FakeController(),
    )

    monitor.process_candle(
        "IPOONE",
        candle("IPOONE", 125),
    )

    state = monitor.get_state(
        "IPOONE"
    )

    assert state["symbol"] == "IPOONE"
    assert state["running"] is True
    assert state["last_candle"]["close"] == 125
    assert state["last_decision"]["action"] == "HOLD"


def test_stop_prevents_processing():
    monitor = MultiIPOLiveMonitor()

    controller = FakeController()

    monitor.register(
        "IPOONE",
        controller,
    )

    monitor.stop("IPOONE")

    result = monitor.process_candle(
        "IPOONE",
        candle("IPOONE", 100),
    )

    assert result is None
    assert len(controller.candles) == 0


def test_start_reenables_processing():
    monitor = MultiIPOLiveMonitor()

    controller = FakeController()

    monitor.register(
        "IPOONE",
        controller,
    )

    monitor.stop("IPOONE")
    monitor.start("IPOONE")

    result = monitor.process_candle(
        "IPOONE",
        candle("IPOONE", 100),
    )

    assert result is not None
    assert len(controller.candles) == 1


def test_unregister_removes_ipo():
    monitor = MultiIPOLiveMonitor()

    monitor.register(
        "IPOONE",
        FakeController(),
    )

    monitor.unregister("IPOONE")

    assert monitor.count() == 0
    assert not monitor.contains("IPOONE")


def test_reset_one_ipo():
    monitor = MultiIPOLiveMonitor()

    monitor.register(
        "IPOONE",
        FakeController(),
    )

    monitor.register(
        "IPOTWO",
        FakeController(),
    )

    monitor.process_candle(
        "IPOONE",
        candle("IPOONE", 100),
    )

    monitor.process_candle(
        "IPOTWO",
        candle("IPOTWO", 200),
    )

    monitor.reset("IPOONE")

    assert (
        monitor.get_state("IPOONE")["last_candle"]
        is None
    )

    assert (
        monitor.get_state("IPOTWO")["last_candle"]
        is not None
    )


def test_clear_removes_all_ipos():
    monitor = MultiIPOLiveMonitor()

    monitor.register(
        "IPOONE",
        FakeController(),
    )

    monitor.register(
        "IPOTWO",
        FakeController(),
    )

    monitor.clear()

    assert monitor.count() == 0
    assert monitor.symbols() == []


def test_unknown_ipo_rejected():
    monitor = MultiIPOLiveMonitor()

    try:
        monitor.process_candle(
            "UNKNOWN",
            candle("UNKNOWN", 100),
        )
        assert False
    except KeyError:
        assert True