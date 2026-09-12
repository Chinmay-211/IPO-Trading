
from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from backend.services.extended_live_paper_trading import (
    ExtendedLivePaperTrading,
)


class FakeExecutionService:
    def __init__(self):
        self.positions: dict[str, dict[str, Any]] = {}
        self.orders: list[dict[str, Any]] = []
        self.realized_pnl = 0.0

    def execute_decision(
        self,
        decision: dict[str, Any],
        timestamp: datetime,
    ) -> dict[str, Any]:
        action = decision["action"]
        symbol = decision["symbol"]
        quantity = int(decision["quantity"])
        price = float(decision["price"])

        if action == "ENTRY":
            self.positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "entry_price": price,
            }

        elif action == "EXIT":
            position = self.positions.pop(symbol, None)

            if position is not None:
                self.realized_pnl += (
                    price - float(position["entry_price"])
                ) * int(position["quantity"])

        result = {
            **decision,
            "executed": True,
            "timestamp": timestamp,
        }

        self.orders.append(result)

        return result

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        return self.positions.get(symbol)

    def get_realized_pnl(self) -> float:
        return self.realized_pnl


class FakeRunner:
    def __init__(
        self,
        symbol: str,
        quantity: int,
        execution_service: FakeExecutionService,
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.execution_service = execution_service

        self.last_candle = None
        self.last_result = None
        self.running = False

    def start(
        self,
        correlation_id: str | None = None,
        mode: int = 1,
    ) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def process_candle(
        self,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:
        self.last_candle = dict(candle)

        result = {
            "action": "HOLD",
            "symbol": self.symbol,
            "price": float(candle["close"]),
            "timestamp": candle["timestamp"],
        }

        self.last_result = result

        return result

    def get_state(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "running": self.running,
            "last_candle": self.last_candle,
            "last_result": self.last_result,
        }

    def get_orders(self) -> list[dict[str, Any]]:
        return list(self.execution_service.orders)

    def get_position(self) -> dict[str, Any] | None:
        return self.execution_service.get_position(
            self.symbol
        )

    def get_realized_pnl(self) -> float:
        return self.execution_service.get_realized_pnl()

    def reset(self) -> None:
        self.last_candle = None
        self.last_result = None
        self.running = False


class FakeSessionService:
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15

    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30

    def __init__(self):
        self.runners: dict[str, FakeRunner] = {}
        self.executions: dict[str, FakeExecutionService] = {}
        self.last_candle = None
        self.last_result = None
        self.session_closed = False

    def register_ipo(
        self,
        symbol: str,
        quantity: int,
    ) -> FakeRunner:
        execution = FakeExecutionService()

        runner = FakeRunner(
            symbol=symbol.upper(),
            quantity=quantity,
            execution_service=execution,
        )

        self.runners[symbol.upper()] = runner
        self.executions[symbol.upper()] = execution

        return runner

    def is_before_market_open(
        self,
        timestamp: datetime,
    ) -> bool:
        current = (
            timestamp.hour,
            timestamp.minute,
        )

        return current < (
            self.MARKET_OPEN_HOUR,
            self.MARKET_OPEN_MINUTE,
        )

    def is_after_market_close(
        self,
        timestamp: datetime,
    ) -> bool:
        current = (
            timestamp.hour,
            timestamp.minute,
        )

        return current >= (
            self.MARKET_CLOSE_HOUR,
            self.MARKET_CLOSE_MINUTE,
        )

    def is_market_open(
        self,
        timestamp: datetime,
    ) -> bool:
        return not (
            self.is_before_market_open(timestamp)
            or self.is_after_market_close(timestamp)
        )

    def process_candle(
        self,
        symbol: str,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:
        symbol = symbol.upper()

        runner = self.runners.get(symbol)

        if runner is None:
            raise ValueError(
                f"IPO runner is not registered: {symbol}"
            )

        self.last_candle = dict(candle)

        result = runner.process_candle(candle)

        self.last_result = result

        return result

    def force_exit(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
    ) -> dict[str, Any] | None:
        symbol = symbol.upper()

        runner = self.runners.get(symbol)

        if runner is None:
            raise ValueError(
                f"IPO runner is not registered: {symbol}"
            )

        execution = self.executions[symbol]

        position = execution.get_position(symbol)

        if position is None:
            self.session_closed = True

            return None

        result = execution.execute_decision(
            {
                "action": "EXIT",
                "symbol": symbol,
                "quantity": int(position["quantity"]),
                "price": float(price),
                "reason": "End-of-day force exit.",
            },
            timestamp=timestamp,
        )

        result["action"] = "EOD_EXIT"
        result["eod_force_exit"] = True

        self.session_closed = True
        self.last_result = result

        return result

    def get_state(self) -> dict[str, Any]:
        return {
            "running": not self.session_closed,
            "session_closed": self.session_closed,
            "last_candle": self.last_candle,
            "last_result": self.last_result,
            "ipos": {
                symbol: runner.get_state()
                for symbol, runner in self.runners.items()
            },
        }

    def reset(self) -> None:
        for runner in self.runners.values():
            runner.reset()

        self.runners.clear()
        self.executions.clear()

        self.last_candle = None
        self.last_result = None
        self.session_closed = False


def make_candle(
    symbol: str,
    hour: int,
    minute: int,
    price: float,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "timestamp": datetime(
            2026,
            8,
            31,
            hour,
            minute,
        ),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 1000,
    }


def make_service():
    service = FakeSessionService()

    service.register_ipo(
        "IPOONE",
        10,
    )

    service.register_ipo(
        "IPOTWO",
        20,
    )

    return service


def test_runner_processes_multiple_candles():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    candle_one = make_candle(
        "IPOONE",
        9,
        16,
        100,
    )

    candle_two = make_candle(
        "IPOONE",
        9,
        17,
        101,
    )

    result_one = runner.process_candle(
        candle_one
    )

    result_two = runner.process_candle(
        candle_two
    )

    assert result_one is not None
    assert result_two is not None

    assert runner.candles_processed == 2
    assert len(runner.results) == 2

    assert (
        service.last_candle["symbol"]
        == "IPOONE"
    )


def test_runner_supports_multiple_ipos():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    runner.process_candle(
        make_candle(
            "IPOONE",
            9,
            16,
            100,
        )
    )

    runner.process_candle(
        make_candle(
            "IPOTWO",
            9,
            17,
            200,
        )
    )

    state = service.get_state()

    assert runner.candles_processed == 2

    assert (
        state["ipos"]["IPOONE"]["last_candle"]["symbol"]
        == "IPOONE"
    )

    assert (
        state["ipos"]["IPOTWO"]["last_candle"]["symbol"]
        == "IPOTWO"
    )


def test_pre_open_candle_is_ignored():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    result = runner.process_candle(
        make_candle(
            "IPOONE",
            8,
            59,
            100,
        )
    )

    state = service.get_state()

    assert result is None

    assert runner.candles_processed == 0
    assert runner.results == []

    assert state["last_candle"] is None
    assert state["last_result"] is None


def test_after_close_forces_open_position_exit():
    service = make_service()

    execution = service.executions["IPOONE"]

    execution.execute_decision(
        {
            "action": "ENTRY",
            "symbol": "IPOONE",
            "quantity": 10,
            "price": 100,
        },
        timestamp=datetime(
            2026,
            8,
            31,
            9,
            20,
        ),
    )

    assert execution.get_position("IPOONE") is not None

    runner = ExtendedLivePaperTrading(
        service
    )

    result = runner.process_candle(
        make_candle(
            "IPOONE",
            15,
            30,
            105,
        )
    )

    assert result is not None
    assert result["action"] == "EOD_EXIT"
    assert result["eod_force_exit"] is True

    assert (
        execution.get_position("IPOONE")
        is None
    )

    assert execution.get_realized_pnl() == 50.0

    assert service.session_closed is True


def test_runner_reset_clears_statistics():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    runner.process_candle(
        make_candle(
            "IPOONE",
            9,
            16,
            100,
        )
    )

    assert runner.candles_processed == 1
    assert len(runner.results) == 1

    runner.reset()

    assert runner.candles_processed == 0
    assert runner.results == []

    state = service.get_state()

    assert state["last_candle"] is None
    assert state["last_result"] is None
    assert state["session_closed"] is False
    assert state["ipos"] == {}


def test_runner_report_contains_session_state():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    runner.process_candle(
        make_candle(
            "IPOONE",
            9,
            16,
            100,
        )
    )

    report = runner.get_report()

    assert report["candles_processed"] == 1
    assert report["results_count"] == 1

    assert report["running"] is True
    assert report["session_closed"] is False

    assert "ipos" in report
    assert "IPOONE" in report["ipos"]


def test_invalid_candle_is_rejected():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    with pytest.raises(ValueError):
        runner.process_candle(
            "not a candle"
        )


def test_invalid_symbol_is_rejected():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    with pytest.raises(ValueError):
        runner.process_candle(
            {
                "symbol": "",
                "timestamp": datetime(
                    2026,
                    8,
                    31,
                    9,
                    16,
                ),
                "close": 100,
            }
        )


def test_invalid_timestamp_is_rejected():
    service = make_service()

    runner = ExtendedLivePaperTrading(
        service
    )

    with pytest.raises(TypeError):
        runner.process_candle(
            {
                "symbol": "IPOONE",
                "timestamp": "09:16",
                "close": 100,
            }
        )
