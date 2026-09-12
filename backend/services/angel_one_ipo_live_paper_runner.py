from __future__ import annotations

from typing import Any

from backend.collectors.market.angel_one_websocket import (
    AngelOneWebSocket,
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


class AngelOneIPOLivePaperRunner:
    """
    Connects Angel One live market data to IPO paper trading.

    Flow:

        Angel One WebSocket
                ↓
        1-minute candle
                ↓
        IPOLivePaperPipeline
                ↓
        IPO live strategy
                ↓
        paper execution
                ↓
        PaperBroker

    SAFETY:
        This class NEVER sends real orders.
        AngelOneWebSocket is used only for market data.
    """

    def __init__(
        self,
        symbol: str,
        quantity: int,
        exchange_type: int,
        instrument_token: str,
        execution_service: IPOLivePaperExecutionService,
        screening_passed: bool = True,
    ):
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if int(quantity) <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        if int(exchange_type) <= 0:
            raise ValueError(
                "exchange_type must be greater than zero."
            )

        if not str(instrument_token).strip():
            raise ValueError(
                "instrument_token is required."
            )

        if execution_service is None:
            raise ValueError(
                "execution_service is required."
            )

        if not isinstance(
            execution_service,
            IPOLivePaperExecutionService,
        ):
            raise TypeError(
                "execution_service must be an "
                "IPOLivePaperExecutionService."
            )

        self.symbol = symbol.strip().upper()
        self.quantity = int(quantity)
        self.exchange_type = int(exchange_type)
        self.instrument_token = str(
            instrument_token
        ).strip()

        self.execution_service = execution_service

        self.strategy_controller = (
            IPOLiveListingStrategyController(
                symbol=self.symbol,
                quantity=self.quantity,
                screening_passed=screening_passed,
            )
        )

        self.pipeline = IPOLivePaperPipeline(
            strategy_controller=self.strategy_controller,
            execution_service=self.execution_service,
        )

        self.websocket = AngelOneWebSocket(
            on_candle=self._on_candle,
        )

        self.running = False

        self.last_candle: dict[str, Any] | None = None
        self.last_result: dict[str, Any] | None = None

    def start(
        self,
        correlation_id: str | None = None,
        mode: int = 1,
    ) -> None:
        """
        Authenticate, connect and subscribe to the IPO.

        This starts market-data collection only.
        Orders remain paper orders.
        """

        if self.running:
            return

        if correlation_id is None:
            correlation_id = (
                f"IPO_PAPER_{self.instrument_token}"
            )

        self.websocket.connect()

        self.websocket.subscribe(
            correlation_id=correlation_id,
            exchange_type=self.exchange_type,
            tokens=[self.instrument_token],
            mode=mode,
        )

        self.running = True

    def _on_candle(
        self,
        candle: Any,
    ) -> None:
        """
        Receive completed candle from Angel One.

        AngelOneWebSocket may provide its own LiveCandle
        object, so convert it into the dictionary format
        expected by the live strategy pipeline.
        """

        normalized = self._normalize_candle(
            candle
        )

        if normalized is None:
            return

        self.last_candle = normalized

        result = self.pipeline.process_candle(
            normalized
        )

        if result is not None:
            self.last_result = result

    @staticmethod
    def _normalize_candle(
        candle: Any,
    ) -> dict[str, Any] | None:
        """
        Convert AngelOne LiveCandle/dict into the
        pipeline candle format.
        """

        if isinstance(candle, dict):
            data = candle

            timestamp = data.get("timestamp")

            open_price = data.get(
                "open_price",
                data.get("open"),
            )
            high_price = data.get(
                "high_price",
                data.get("high"),
            )
            low_price = data.get(
                "low_price",
                data.get("low"),
            )
            close_price = data.get(
                "close_price",
                data.get("close"),
            )
            volume = data.get("volume")

            symbol = data.get("symbol")

        else:
            timestamp = getattr(
                candle,
                "timestamp",
                None,
            )

            open_price = getattr(
                candle,
                "open_price",
                getattr(candle, "open", None),
            )

            high_price = getattr(
                candle,
                "high_price",
                getattr(candle, "high", None),
            )

            low_price = getattr(
                candle,
                "low_price",
                getattr(candle, "low", None),
            )

            close_price = getattr(
                candle,
                "close_price",
                getattr(candle, "close", None),
            )

            volume = getattr(
                candle,
                "volume",
                None,
            )

            symbol = getattr(
                candle,
                "symbol",
                None,
            )

        if timestamp is None:
            return None

        if (
            open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
        ):
            return None

        result = {
            "symbol": (
                str(symbol).strip().upper()
                if symbol
                else self_symbol_fallback()
            ),
            "timestamp": timestamp,
            "open_price": float(open_price),
            "high_price": float(high_price),
            "low_price": float(low_price),
            "close_price": float(close_price),
            "volume": (
                int(volume)
                if volume is not None
                else None
            ),
        }

        return result

    def stop(self) -> None:
        """
        Stop market-data collection.

        Does not place any broker order.
        """

        if not self.running:
            self.websocket.close()
            return

        self.websocket.close()
        self.running = False

    def flush(self) -> dict[str, Any] | None:
        """
        Flush the currently building WebSocket candle.

        Useful at the end of a session.
        """

        candles = self.websocket.get_candles(
            symbol=self.instrument_token
        )

        if not candles:
            return None

        candle = candles[-1]

        self._on_candle(candle)

        return self.last_result

    def get_state(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "instrument_token": self.instrument_token,
            "exchange_type": self.exchange_type,
            "running": self.running,
            "websocket_connected": (
                self.websocket.connected
            ),
            "websocket_subscribed": (
                self.websocket.subscribed
            ),
            "last_candle": self.last_candle,
            "last_result": self.last_result,
            "pipeline": self.pipeline.get_state(),
        }

    def get_orders(self) -> list[dict[str, Any]]:
        return self.pipeline.get_orders()

    def get_position(
        self,
    ) -> dict[str, Any] | None:
        return self.pipeline.get_position(
            self.symbol
        )

    def get_realized_pnl(self) -> float:
        return self.pipeline.get_realized_pnl()

    def reset(self) -> None:
        """
        Reset strategy, candles and paper execution.
        """

        self.websocket.reset()
        self.pipeline.reset()

        self.last_candle = None
        self.last_result = None
        self.running = False


def self_symbol_fallback() -> str:
    """
    Fallback used when an incoming candle does not
    contain a symbol.
    """

    return "UNKNOWN"