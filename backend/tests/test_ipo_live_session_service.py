from __future__ import annotations

from backend.services.ipo_live_session_service import (
    IPOLiveSessionService,
)


class FakeDiscovery:
    def run(self):
        return [
            {
                "symbol": "IPOONE",
            },
            {
                "symbol": "IPOTWO",
            },
        ]


class FakeResolver:
    def find_token(self, symbol):
        return {
            "token": f"TOKEN_{symbol}",
            "symbol": symbol,
        }


class FakeRunner:
    def __init__(
        self,
        symbol,
        quantity,
        exchange_type,
        instrument_token,
        screening_passed=True,
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.exchange_type = exchange_type
        self.instrument_token = instrument_token
        self.screening_passed = screening_passed

        self.running = False
        self.orders = []
        self.pnl = 0.0
        self.reset_called = False

    def start(
        self,
        correlation_id=None,
        mode=1,
    ):
        self.running = True

    def stop(self):
        self.running = False

    def get_state(self):
        return {
            "symbol": self.symbol,
            "running": self.running,
        }

    def get_orders(self):
        return list(self.orders)

    def get_realized_pnl(self):
        return self.pnl

    def reset(self):
        self.running = False
        self.orders.clear()
        self.pnl = 0.0
        self.reset_called = True


def make_service():
    return IPOLiveSessionService(
        discovery_service=FakeDiscovery(),
        token_resolver=FakeResolver(),
        runner_factory=FakeRunner,
    )


def test_discover():
    service = make_service()

    result = service.discover()

    assert len(result) == 2
    assert result[0]["symbol"] == "IPOONE"


def test_register_ipo():
    service = make_service()

    runner = service.register_ipo(
        {
            "symbol": "IPOONE",
        },
        quantity=100,
    )

    assert runner.symbol == "IPOONE"
    assert runner.quantity == 100
    assert runner.instrument_token == "TOKEN_IPOONE"

    assert "IPOONE" in service.runners


def test_register_multiple_ipos():
    service = make_service()

    service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    service.register_ipo(
        {"symbol": "IPOTWO"},
        quantity=200,
    )

    assert len(service.runners) == 2


def test_start_one():
    service = make_service()

    service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    service.start("IPOONE")

    assert service.runners["IPOONE"].running is True


def test_stop_one():
    service = make_service()

    service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    service.start("IPOONE")
    service.stop("IPOONE")

    assert service.runners["IPOONE"].running is False


def test_start_all():
    service = make_service()

    service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    service.register_ipo(
        {"symbol": "IPOTWO"},
        quantity=200,
    )

    service.start_all()

    assert service.runners["IPOONE"].running is True
    assert service.runners["IPOTWO"].running is True


def test_stop_all():
    service = make_service()

    service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    service.register_ipo(
        {"symbol": "IPOTWO"},
        quantity=200,
    )

    service.start_all()
    service.stop_all()

    assert service.runners["IPOONE"].running is False
    assert service.runners["IPOTWO"].running is False


def test_state():
    service = make_service()

    service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    state = service.get_state()

    assert state["count"] == 1
    assert "IPOONE" in state["ipos"]


def test_combined_orders():
    service = make_service()

    first = service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    second = service.register_ipo(
        {"symbol": "IPOTWO"},
        quantity=200,
    )

    first.orders.append(
        {
            "symbol": "IPOONE",
            "side": "BUY",
        }
    )

    second.orders.append(
        {
            "symbol": "IPOTWO",
            "side": "BUY",
        }
    )

    orders = service.get_orders()

    assert len(orders) == 2


def test_combined_pnl():
    service = make_service()

    first = service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    second = service.register_ipo(
        {"symbol": "IPOTWO"},
        quantity=200,
    )

    first.pnl = 500.0
    second.pnl = -200.0

    assert service.get_realized_pnl() == 300.0


def test_reset():
    service = make_service()

    runner = service.register_ipo(
        {"symbol": "IPOONE"},
        quantity=100,
    )

    service.reset()

    assert runner.reset_called is True
    assert service.runners == {}
    assert service.metadata == {}


def test_missing_symbol():
    service = make_service()

    try:
        service.register_ipo(
            {},
            quantity=100,
        )
    except ValueError as exc:
        assert "symbol" in str(exc).lower()
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_missing_token():
    class EmptyResolver:
        def find_token(self, symbol):
            return None

    service = IPOLiveSessionService(
        discovery_service=FakeDiscovery(),
        token_resolver=EmptyResolver(),
        runner_factory=FakeRunner,
    )

    try:
        service.register_ipo(
            {"symbol": "IPOONE"},
            quantity=100,
        )
    except ValueError as exc:
        assert "instrument" in str(exc).lower()
    else:
        raise AssertionError(
            "Expected ValueError"
        )