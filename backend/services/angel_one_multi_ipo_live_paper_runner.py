from __future__ import annotations

from typing import Any

from backend.collectors.market.angel_one_token_resolver import (
    AngelOneTokenResolver,
)
from backend.collectors.market.angel_one_websocket import (
    AngelOneWebSocket,
)
from backend.services.ipo_live_listing_strategy_controller import (
    IPOLiveListingStrategyController,
)
from backend.services.multi_ipo_live_monitor import (
    MultiIPOLiveMonitor,
)
from backend.services.multi_ipo_live_performance import (
    MultiIPOLivePerformance,
)


class AngelOneMultiIPOLivePaperRunner:
    """
    Connects one Angel One WebSocket to multiple IPO
    live paper-trading controllers.

    Flow:

        Angel One WebSocket
                |
                v
        Live 1-minute candle
                |
                v
        Instrument token
                |
                v
        AngelOneTokenResolver
                |
                v
        IPO symbol
                |
                v
        MultiIPOLiveMonitor
                |
                v
        IPO strategy/controller
                |
                v
        Paper execution

    SAFETY:

        This class uses Angel One only for market data.

        It NEVER places real broker orders.
    """

    def __init__(
        self,
        monitor: MultiIPOLiveMonitor | None = None,
        token_resolver: AngelOneTokenResolver | None = None,
        websocket: AngelOneWebSocket | None = None,
    ):
        self.monitor = (
            monitor
            if monitor is not None
            else MultiIPOLiveMonitor(
                on_result=self._on_result,
            )
        )

        self.token_resolver = (
            token_resolver
            if token_resolver is not None
            else AngelOneTokenResolver()
        )

        self.websocket = (
            websocket
            if websocket is not None
            else AngelOneWebSocket(
                on_candle=self._on_candle,
            )
        )

        self._token_to_symbol: dict[str, str] = {}
        self._symbol_to_token: dict[str, str] = {}

        self.running = False
        self.last_result: dict[str, Any] | None = None

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        if not isinstance(symbol, str):
            raise ValueError(
                "symbol must be a string."
            )

        symbol = symbol.strip().upper()

        if not symbol:
            raise ValueError(
                "symbol is required."
            )

        return symbol

    @staticmethod
    def _normalize_token(
        token: str | int,
    ) -> str:
        token = str(token).strip()

        if not token:
            raise ValueError(
                "instrument_token is required."
            )

        return token

    def register_ipo(
        self,
        symbol: str,
        quantity: int,
        exchange_type: int,
        instrument_token: str | int,
        screening_passed: bool = True,
        controller: Any | None = None,
    ) -> None:
        """
        Register one IPO for live paper trading.

        If a controller is not supplied, a standard
        IPOLiveListingStrategyController is created.
        """

        symbol = self._normalize_symbol(symbol)

        token = self._normalize_token(
            instrument_token
        )

        quantity = int(quantity)

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        exchange_type = int(exchange_type)

        if exchange_type <= 0:
            raise ValueError(
                "exchange_type must be greater than zero."
            )

        if self.monitor.contains(symbol):
            raise ValueError(
                f"IPO already registered: {symbol}"
            )

        if token in self._token_to_symbol:
            raise ValueError(
                "instrument_token is already "
                "registered."
            )

        if controller is None:
            controller = (
                IPOLiveListingStrategyController(
                    symbol=symbol,
                    quantity=quantity,
                    screening_passed=screening_passed,
                )
            )

        if not hasattr(
            controller,
            "process_candle",
        ):
            raise TypeError(
                "controller must expose "
                "process_candle()."
            )

        self.monitor.register(
            symbol=symbol,
            controller=controller,
        )

        self._token_to_symbol[token] = symbol
        self._symbol_to_token[symbol] = token

        instrument = self.token_resolver.find(
            token
        )

        if instrument is not None:
            resolved_symbol = instrument.get(
                "symbol"
            )

            if resolved_symbol:
                resolved_symbol = (
                    str(resolved_symbol)
                    .strip()
                    .upper()
                )

                if resolved_symbol != symbol:
                    raise ValueError(
                        "Instrument token resolves to "
                        f"{resolved_symbol}, not {symbol}."
                    )

    def unregister_ipo(
        self,
        symbol: str,
    ) -> None:
        symbol = self._normalize_symbol(
            symbol
        )

        token = self._symbol_to_token.pop(
            symbol,
            None,
        )

        self._token_to_symbol.pop(
            token,
            None,
        )

        self.monitor.unregister(
            symbol
        )

    def symbols(self) -> list[str]:
        return self.monitor.symbols()

    def count(self) -> int:
        return self.monitor.count()

    def start(
        self,
        correlation_id: str = "IPO_MULTI_PAPER",
        mode: int = 1,
    ) -> None:
        """
        Start the shared Angel One WebSocket and
        subscribe to all registered IPO tokens.
        """

        if self.running:
            return

        if self.count() == 0:
            raise RuntimeError(
                "No IPOs are registered."
            )

        tokens = list(
            self._token_to_symbol.keys()
        )

        self.websocket.connect()

        self.websocket.subscribe(
            correlation_id=correlation_id,
            exchange_type=1,
            tokens=tokens,
            mode=mode,
        )

        self.running = True

    def stop(self) -> None:
        """
        Stop market-data collection.

        No real broker order is placed.
        """

        self.websocket.close()
        self.running = False

    def _on_candle(
        self,
        candle: Any,
    ) -> None:
        """
        Receive a completed candle from Angel One
        and route it to the correct IPO.
        """

        normalized = (
            self._normalize_candle(candle)
        )

        if normalized is None:
            return

        token = normalized["_instrument_token"]

        symbol = self._token_to_symbol.get(
            token
        )

        if symbol is None:
            symbol = (
                self.token_resolver.resolve(
                    token
                )
            )

        if symbol is None:
            return

        if not self.monitor.contains(
            symbol
        ):
            return

        normalized.pop(
            "_instrument_token",
            None,
        )

        result = self.monitor.process_candle(
            symbol=symbol,
            candle=normalized,
        )

        if isinstance(result, dict):
            self.last_result = result

    def _on_result(
        self,
        symbol: str,
        result: dict[str, Any] | None,
    ) -> None:
        if isinstance(result, dict):
            self.last_result = result

    def _normalize_candle(
        self,
        candle: Any,
    ) -> dict[str, Any] | None:
        """
        Normalize an Angel One LiveCandle/dict.

        The instrument token is retained internally as
        _instrument_token for routing.
        """

        if isinstance(candle, dict):
            data = candle

            timestamp = data.get(
                "timestamp"
            )

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

            volume = data.get(
                "volume"
            )

            token = (
                data.get("instrument_token")
                or data.get("token")
                or data.get("symbol")
            )

        else:
            timestamp = getattr(
                candle,
                "timestamp",
                None,
            )

            open_price = getattr(
                candle,
                "open_price",
                getattr(
                    candle,
                    "open",
                    None,
                ),
            )

            high_price = getattr(
                candle,
                "high_price",
                getattr(
                    candle,
                    "high",
                    None,
                ),
            )

            low_price = getattr(
                candle,
                "low_price",
                getattr(
                    candle,
                    "low",
                    None,
                ),
            )

            close_price = getattr(
                candle,
                "close_price",
                getattr(
                    candle,
                    "close",
                    None,
                ),
            )

            volume = getattr(
                candle,
                "volume",
                None,
            )

            token = (
                getattr(
                    candle,
                    "instrument_token",
                    None,
                )
                or getattr(
                    candle,
                    "token",
                    None,
                )
                or getattr(
                    candle,
                    "symbol",
                    None,
                )
            )

        if timestamp is None:
            return None

        if token is None:
            return None

        if (
            open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
        ):
            return None

        try:
            open_price = float(
                open_price
            )
            high_price = float(
                high_price
            )
            low_price = float(
                low_price
            )
            close_price = float(
                close_price
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if volume is not None:
            try:
                volume = int(volume)
            except (
                TypeError,
                ValueError,
            ):
                volume = None

        return {
            "_instrument_token": str(
                token
            ).strip(),
            "timestamp": timestamp,
            "open_price": open_price,
            "high_price": high_price,
            "low_price": low_price,
            "close_price": close_price,
            "volume": volume,
        }

    def get_state(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        if symbol is not None:
            symbol = self._normalize_symbol(
                symbol
            )

        return {
            "running": self.running,
            "count": self.count(),
            "symbols": self.symbols(),
            "token_to_symbol": dict(
                self._token_to_symbol
            ),
            "symbol_to_token": dict(
                self._symbol_to_token
            ),
            "websocket_connected": (
                self.websocket.connected
            ),
            "websocket_subscribed": (
                self.websocket.subscribed
            ),
            "last_result": self.last_result,
            "monitor": self.monitor.get_state(
                symbol
            ),
        }

    def get_performance(
        self,
    ) -> dict[str, Any]:
        performance = (
            MultiIPOLivePerformance(
                self.monitor
            )
        )

        return performance.get_report()

    def get_symbol_performance(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        symbol = self._normalize_symbol(
            symbol
        )

        performance = (
            MultiIPOLivePerformance(
                self.monitor
            )
        )

        return performance.get_symbol_report(
            symbol
        )

    def reset(
        self,
    ) -> None:
        """
        Reset monitoring state and paper state.

        Registered IPOs remain registered.
        """

        self.websocket.reset()
        self.monitor.reset()

        self.last_result = None
        self.running = False