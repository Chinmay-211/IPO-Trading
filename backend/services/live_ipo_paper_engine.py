from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.collectors.market_data.one_minute_candle_builder import (
    OneMinuteCandleBuilder,
)
from backend.services.ipo_live_paper_pipeline import (
    IPOLivePaperPipeline,
)
from backend.services.market_session_service import (
    MarketSessionService,
)


class LiveIPOPaperEngine:
    """
    Connects live ticks to IPO paper-trading pipelines with session management.

    Flow:

        tick
          ↓
        session check
          ↓
        candle builder
          ↓
        completed 1-minute candle
          ↓
        IPO paper pipeline
          ↓
        strategy
          ↓
        paper execution

    PAPER TRADING ONLY.
    """

    def __init__(
        self,
        pipelines: dict[str, IPOLivePaperPipeline],
        candle_builder: OneMinuteCandleBuilder | None = None,
        session_service: MarketSessionService | None = None,
    ):
        if not isinstance(pipelines, dict):
            raise ValueError("pipelines must be a dictionary.")

        normalized = {}

        for symbol, pipeline in pipelines.items():
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError(
                    "pipeline symbol must be a non-empty string."
                )

            if not isinstance(pipeline, IPOLivePaperPipeline):
                raise TypeError(
                    "pipelines must contain "
                    "IPOLivePaperPipeline instances."
                )

            normalized[symbol.strip().upper()] = pipeline

        self.pipelines = normalized

        self.candle_builder = (
            candle_builder
            if candle_builder is not None
            else OneMinuteCandleBuilder()
        )

        if session_service is not None and not isinstance(
            session_service, MarketSessionService
        ):
            raise TypeError(
                "session_service must be a MarketSessionService."
            )

        self.session_service = (
            session_service
            if session_service is not None
            else MarketSessionService()
        )

        self.running = False
        self.session_closed = False
        self.ticks_processed = 0
        self.candles_completed = 0
        self.decisions_processed = 0
        self.results: list[dict[str, Any]] = []
        self.last_results: dict[str, Any] = {}
        self.ipos_decisions: dict[str, int] = {
            symbol: 0 for symbol in self.pipelines
        }

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def close_session(
        self,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        self.running = False
        self.session_closed = True

        return {
            "action": "SESSION_CLOSED",
            "timestamp": timestamp,
        }

    def get_session_state(
        self,
        timestamp: datetime,
    ) -> str:
        return self.session_service.get_session_state(timestamp)

    def process_tick(
        self,
        tick: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(tick, dict):
            raise ValueError("tick must be a dictionary.")

        if "symbol" not in tick:
            raise ValueError("tick symbol is required.")

        symbol = tick["symbol"]

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("tick symbol is required.")

        symbol = symbol.strip().upper()

        if symbol not in self.pipelines:
            raise KeyError(
                f"No paper pipeline configured for {symbol}."
            )

        if "timestamp" not in tick:
            raise TypeError("tick timestamp is required.")

        timestamp = tick["timestamp"]

        if not isinstance(timestamp, datetime):
            raise TypeError("tick timestamp must be a datetime.")

        if "price" not in tick:
            raise ValueError("tick price is required.")

        price = tick["price"]

        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError("tick price must be a positive number.")

        if "volume" not in tick:
            raise ValueError("tick volume is required.")

        volume = tick["volume"]

        if not isinstance(volume, int) or volume < 0:
            raise ValueError("tick volume must be a non-negative integer.")

        if not self.running or self.session_closed:
            return None

        if not self.session_service.is_market_open(timestamp):
            return None

        self.ticks_processed += 1

        completed = self.candle_builder.update(tick)

        if completed is None:
            return None

        self.candles_completed += 1

        candle = self._candle_to_dict(completed)

        result = self.pipelines[symbol].process_candle(candle)

        if result is not None:
            self.decisions_processed += 1
            self.last_results[symbol] = result
            self.ipos_decisions[symbol] = (
                self.ipos_decisions.get(symbol, 0) + 1
            )

        record = {
            "symbol": symbol,
            "candle": candle,
            "result": result,
        }

        self.results.append(record)

        return result

    @staticmethod
    def _candle_to_dict(
        candle: Any,
    ) -> dict[str, Any]:
        return {
            "symbol": candle.symbol,
            "timestamp": candle.timestamp,
            "open_price": candle.open,
            "high_price": candle.high,
            "low_price": candle.low,
            "close_price": candle.close,
            "volume": candle.volume,
            "interval": candle.interval,
            "source": candle.source,
        }

    def flush(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        if symbol is None:
            symbols = list(self.pipelines)
        else:
            symbols = [symbol.strip().upper()]

        results = {}

        for current_symbol in symbols:
            if current_symbol not in self.pipelines:
                continue

            candle = self.candle_builder.flush(current_symbol)

            if candle is None:
                continue

            self.candles_completed += 1

            candle_dict = self._candle_to_dict(candle)

            result = self.pipelines[
                current_symbol
            ].process_candle(candle_dict)

            if result is not None:
                self.decisions_processed += 1
                self.last_results[current_symbol] = result
                self.ipos_decisions[current_symbol] = (
                    self.ipos_decisions.get(current_symbol, 0) + 1
                )

            record = {
                "symbol": current_symbol,
                "candle": candle_dict,
                "result": result,
            }

            self.results.append(record)
            results[current_symbol] = result

        return results

    def get_orders(self) -> list[dict[str, Any]]:
        orders = []

        for pipeline in self.pipelines.values():
            for order in pipeline.get_orders():
                order_copy = dict(order)
                if "action" not in order_copy and "side" in order_copy:
                    order_copy["action"] = order_copy["side"]
                orders.append(order_copy)

        return orders

    def get_positions(
        self,
    ) -> dict[str, dict[str, Any] | None]:
        return {
            symbol: pipeline.get_position(symbol)
            for symbol, pipeline in self.pipelines.items()
        }

    def get_realized_pnl(self) -> float:
        return sum(
            pipeline.get_realized_pnl()
            for pipeline in self.pipelines.values()
        )

    def get_state(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "session_closed": self.session_closed,
            "pipelines": list(self.pipelines.keys()),
            "ticks_processed": self.ticks_processed,
            "candles_completed": self.candles_completed,
            "decisions_processed": self.decisions_processed,
            "results_count": len(self.results),
            "last_results": dict(self.last_results),
            "orders": self.get_orders(),
            "positions": self.get_positions(),
            "realized_pnl": self.get_realized_pnl(),
            "ipos": {
                symbol: {
                    "decisions": self.ipos_decisions.get(symbol, 0),
                    "orders": pipeline.get_orders(),
                    "position": pipeline.get_position(symbol),
                    "realized_pnl": pipeline.get_realized_pnl(),
                }
                for symbol, pipeline in self.pipelines.items()
            },
        }

    def get_report(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "session_closed": self.session_closed,
            "ipo_count": len(self.pipelines),
            "ticks_processed": self.ticks_processed,
            "candles_completed": self.candles_completed,
            "decisions_processed": self.decisions_processed,
            "order_count": len(self.get_orders()),
            "orders": self.get_orders(),
            "positions": self.get_positions(),
            "realized_pnl": self.get_realized_pnl(),
            "last_results": dict(self.last_results),
        }

    def reset(self) -> None:
        self.running = False
        self.session_closed = False
        self.candle_builder.reset()

        for pipeline in self.pipelines.values():
            pipeline.reset()

        self.ticks_processed = 0
        self.candles_completed = 0
        self.decisions_processed = 0
        self.results.clear()
        self.last_results.clear()
        self.ipos_decisions = {
            symbol: 0 for symbol in self.pipelines
        }