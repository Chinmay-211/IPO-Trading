from __future__ import annotations

from datetime import datetime
from typing import Any


class IPOLiveSessionService:
    """
    Orchestrates IPO listing-day live paper-trading sessions.

    Responsibilities:
        - Discover IPOs when a discovery service is configured.
        - Resolve Angel One instrument tokens.
        - Create paper execution services/runners.
        - Manage multiple IPO runners.
        - Process live candles.
        - Respect market-session boundaries.
        - Ignore candles before market open.
        - Force-close open paper positions after market close.
        - Provide combined session state, orders and P&L.

    SAFETY:
        This service is PAPER TRADING ONLY.
        It never places real broker orders.
    """

    def __init__(
        self,
        discovery_service: Any = None,
        token_resolver: Any = None,
        runner_factory: Any = None,
        execution_service_factory: Any = None,
        session_service: Any = None,
        websocket: Any = None,
    ):
        """
        Create the live IPO paper-trading session.

        Supported construction modes:

        1. Full production mode:

            IPOLiveSessionService(
                discovery_service=...,
                token_resolver=...,
                runner_factory=...,
            )

        2. Extended live-paper test/integration mode:

            IPOLiveSessionService(
                execution_service_factory=...,
                token_resolver=...,
                session_service=...,
                websocket=...,
            )

        The second mode creates runners internally.
        """

        self.discovery_service = discovery_service
        self.token_resolver = token_resolver
        self.runner_factory = runner_factory
        self.execution_service_factory = (
            execution_service_factory
        )
        self.session_service = session_service
        self.websocket = websocket

        self.runners: dict[str, Any] = {}
        self.metadata: dict[str, dict[str, Any]] = {}

        self.last_candle: dict[str, Any] | None = None
        self.last_result: dict[str, Any] | None = None

        self.session_closed = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        if not isinstance(symbol, str):
            raise ValueError(
                "symbol must be a string."
            )

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "symbol is required."
            )

        return normalized

    @staticmethod
    def _get_value(
        item: Any,
        *names: str,
        default: Any = None,
    ) -> Any:
        """
        Read a value from either a dictionary or an object.
        """

        if isinstance(item, dict):
            for name in names:
                if name in item:
                    return item[name]

            return default

        for name in names:
            if hasattr(item, name):
                return getattr(item, name)

        return default

    def _resolve_instrument(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """
        Resolve a symbol through the configured token resolver.
        """

        if self.token_resolver is None:
            return None

        find_token = getattr(
            self.token_resolver,
            "find_token",
            None,
        )

        if callable(find_token):
            instrument = find_token(symbol)

            if instrument is not None:
                if isinstance(instrument, dict):
                    return dict(instrument)

                return {
                    "token": self._get_value(
                        instrument,
                        "token",
                        "instrument_token",
                        "symboltoken",
                    ),
                }

        return None

    def _resolve_token(
        self,
        symbol: str,
    ) -> str:
        """
        Resolve an Angel One instrument token.

        Raises ValueError when the resolver is configured but
        the instrument cannot be found.
        """

        instrument = self._resolve_instrument(
            symbol
        )

        if instrument is None:
            raise ValueError(
                f"Angel One instrument not found for {symbol}."
            )

        token = self._get_value(
            instrument,
            "token",
            "instrument_token",
            "symboltoken",
        )

        if token is None or not str(token).strip():
            raise ValueError(
                f"Angel One token is missing for {symbol}."
            )

        return str(token).strip()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[Any]:
        """
        Discover IPOs using the configured discovery service.

        If no discovery service is configured, return an empty list.
        """

        if self.discovery_service is None:
            return []

        run = getattr(
            self.discovery_service,
            "run",
            None,
        )

        if not callable(run):
            raise TypeError(
                "discovery_service must expose run()."
            )

        result = run()

        if result is None:
            return []

        if isinstance(result, list):
            return result

        return list(result)

    # ------------------------------------------------------------------
    # Runner creation
    # ------------------------------------------------------------------

    def _create_runner(
        self,
        symbol: str,
        quantity: int,
        exchange_type: int,
        token: str,
        screening_passed: bool,
    ) -> Any:
        """
        Create a paper runner.

        Prefer an explicitly supplied runner_factory.

        Otherwise create an AngelOneIPOLivePaperRunner using
        the supplied execution_service_factory.
        """

        if self.runner_factory is not None:
            return self.runner_factory(
                symbol=symbol,
                quantity=int(quantity),
                exchange_type=int(exchange_type),
                instrument_token=token,
                screening_passed=bool(
                    screening_passed
                ),
            )

        if self.execution_service_factory is None:
            raise ValueError(
                "Either runner_factory or "
                "execution_service_factory is required."
            )

        from backend.services.angel_one_ipo_live_paper_runner import (
            AngelOneIPOLivePaperRunner,
        )

        execution_service = (
            self.execution_service_factory(
                symbol,
                int(quantity),
            )
        )

        return AngelOneIPOLivePaperRunner(
            symbol=symbol,
            quantity=int(quantity),
            exchange_type=int(exchange_type),
            instrument_token=token,
            execution_service=execution_service,
            screening_passed=bool(
                screening_passed
            ),
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_ipo(
        self,
        ipo: Any,
        quantity: int,
        exchange_type: int = 1,
        screening_passed: bool = True,
    ) -> Any:
        """
        Register one IPO.

        `ipo` may be:

            "IPOONE"

        or a dictionary/object containing:

            symbol
            trading_symbol
            ticker

        The plain-string form is intentionally supported because
        live paper sessions commonly already know the trading symbol.
        """

        if int(quantity) <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        if int(exchange_type) <= 0:
            raise ValueError(
                "exchange_type must be greater than zero."
            )

        if isinstance(ipo, str):
            symbol = ipo
        else:
            symbol = self._get_value(
                ipo,
                "symbol",
                "trading_symbol",
                "ticker",
            )

        symbol = self._normalize_symbol(
            symbol
        )

        if symbol in self.runners:
            raise ValueError(
                f"IPO already registered: {symbol}"
            )

        token = self._resolve_token(
            symbol
        )

        runner = self._create_runner(
            symbol=symbol,
            quantity=int(quantity),
            exchange_type=int(exchange_type),
            token=token,
            screening_passed=bool(
                screening_passed
            ),
        )

        self.runners[symbol] = runner

        self.metadata[symbol] = {
            "symbol": symbol,
            "quantity": int(quantity),
            "exchange_type": int(exchange_type),
            "instrument_token": token,
            "screening_passed": bool(
                screening_passed
            ),
        }

        return runner

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------

    def _is_market_open(
        self,
        timestamp: datetime,
    ) -> bool:
        """
        Ask the configured market session service whether
        the supplied timestamp is inside the regular session.

        If no session service is configured, candles are accepted.
        """

        if self.session_service is None:
            return True

        method = getattr(
            self.session_service,
            "is_market_open",
            None,
        )

        if not callable(method):
            return True

        return bool(
            method(timestamp)
        )

    def _is_after_market_close(
        self,
        timestamp: datetime,
    ) -> bool:
        """
        Ask the configured session service whether the market
        is after regular close.
        """

        if self.session_service is None:
            return False

        method = getattr(
            self.session_service,
            "is_after_market_close",
            None,
        )

        if not callable(method):
            return False

        return bool(
            method(timestamp)
        )

    # ------------------------------------------------------------------
    # WebSocket callback
    # ------------------------------------------------------------------

    def _normalize_candle(
        self,
        candle: Any,
    ) -> dict[str, Any] | None:
        """
        Normalize a candle from either a dictionary or LiveCandle.
        """

        if isinstance(candle, dict):
            symbol = candle.get(
                "symbol"
            )

            timestamp = candle.get(
                "timestamp"
            )

            open_price = candle.get(
                "open_price",
                candle.get("open"),
            )

            high_price = candle.get(
                "high_price",
                candle.get("high"),
            )

            low_price = candle.get(
                "low_price",
                candle.get("low"),
            )

            close_price = candle.get(
                "close_price",
                candle.get("close"),
            )

            volume = candle.get(
                "volume"
            )

            source = candle.get(
                "source"
            )

        else:
            symbol = getattr(
                candle,
                "symbol",
                None,
            )

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

            source = getattr(
                candle,
                "source",
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
                else None
            ),
            "timestamp": timestamp,
            "open": float(open_price),
            "high": float(high_price),
            "low": float(low_price),
            "close": float(close_price),
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

        if source is not None:
            result["source"] = source

        return result

    def on_candle(
        self,
        candle: Any,
    ) -> dict[str, Any] | None:
        """
        Process one live candle.

        This is the callback intended for WebSocket integrations.

        Pre-open candles are ignored.

        After market close, all open paper positions are force-exited.
        """

        normalized = self._normalize_candle(
            candle
        )

        if normalized is None:
            return None

        self.last_candle = normalized

        symbol = normalized.get(
            "symbol"
        )

        if not symbol:
            return None

        symbol = self._normalize_symbol(
            symbol
        )

        timestamp = normalized.get(
            "timestamp"
        )

        if not isinstance(
            timestamp,
            datetime,
        ):
            return None

        # --------------------------------------------------------------
        # PRE-OPEN
        # --------------------------------------------------------------

        if self.session_service is not None:
            before_open = getattr(
                self.session_service,
                "is_before_market_open",
                None,
            )

            if callable(before_open):
                if before_open(timestamp):
                    return None

        # --------------------------------------------------------------
        # AFTER CLOSE
        # --------------------------------------------------------------

        if self._is_after_market_close(
            timestamp
        ):
            return self._force_exit_symbol(
                symbol=symbol,
                price=float(
                    normalized["close"]
                ),
                timestamp=timestamp,
            )

        # --------------------------------------------------------------
        # REGULAR SESSION
        # --------------------------------------------------------------

        if not self._is_market_open(
            timestamp
        ):
            return None

        runner = self.runners.get(
            symbol
        )

        if runner is None:
            return None

        process_candle = getattr(
            runner,
            "_on_candle",
            None,
        )

        if callable(process_candle):
            process_candle(
                normalized
            )

            result = getattr(
                runner,
                "last_result",
                None,
            )

            self.last_result = result

            return result

        process = getattr(
            runner,
            "process_candle",
            None,
        )

        if callable(process):
            result = process(
                normalized
            )

            self.last_result = result

            return result

        return None

    # Alias used by some WebSocket implementations.

    def _on_candle(
        self,
        candle: Any,
    ) -> dict[str, Any] | None:
        return self.on_candle(
            candle
        )

    # ------------------------------------------------------------------
    # Forced exit
    # ------------------------------------------------------------------

    def _force_exit_symbol(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
    ) -> dict[str, Any] | None:
        """
        Force-close an open position for one IPO.

        First preference is the runner's own force-exit/EOD method.
        Otherwise use the runner's execution service.
        """

        runner = self.runners.get(
            symbol
        )

        if runner is None:
            return None

        execution_service = getattr(
            runner,
            "execution_service",
            None,
        )

        if execution_service is None:
            execution_service = getattr(
                runner,
                "execution",
                None,
            )

        position = None

        if execution_service is not None:
            get_position = getattr(
                execution_service,
                "get_position",
                None,
            )

            if callable(get_position):
                position = get_position(
                    symbol
                )

        if position is None:
            get_position = getattr(
                runner,
                "get_position",
                None,
            )

            if callable(get_position):
                position = get_position(
                    symbol
                )

        if position is None:
            self.session_closed = True

            result = {
                "action": "EOD_EXIT",
                "executed": False,
                "symbol": symbol,
                "quantity": 0,
                "price": price,
                "timestamp": timestamp,
                "order": None,
                "reason": (
                    "No open paper position "
                    "to force exit."
                ),
            }

            self.last_result = result

            return result

        quantity = position.get(
            "quantity",
            0,
        )

        quantity = int(quantity)

        if quantity <= 0:
            self.session_closed = True

            result = {
                "action": "EOD_EXIT",
                "executed": False,
                "symbol": symbol,
                "quantity": 0,
                "price": price,
                "timestamp": timestamp,
                "order": None,
                "reason": (
                    "No open paper position "
                    "to force exit."
                ),
            }

            self.last_result = result

            return result

        # Prefer execution service because it is the paper-only
        # execution boundary.

        if execution_service is not None:
            execute_decision = getattr(
                execution_service,
                "execute_decision",
                None,
            )

            if callable(execute_decision):
                result = execute_decision(
                    {
                        "action": "EXIT",
                        "symbol": symbol,
                        "quantity": quantity,
                        "price": price,
                        "reason": (
                            "End-of-day force exit."
                        ),
                    },
                    timestamp=timestamp,
                )

                if isinstance(
                    result,
                    dict,
                ):
                    result["action"] = (
                        "EOD_EXIT"
                    )
                    result[
                        "eod_force_exit"
                    ] = True

                self.session_closed = True
                self.last_result = result

                return result

        self.session_closed = True

        return None

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def _subscribe_websocket(
        self,
        symbol: str,
        token: str,
        mode: int,
    ) -> None:
        """
        Subscribe the configured WebSocket to one IPO.
        """

        if self.websocket is None:
            return

        subscribe = getattr(
            self.websocket,
            "subscribe",
            None,
        )

        if not callable(subscribe):
            return

        subscribe(
            correlation_id=(
                f"IPO_PAPER_{symbol}"
            ),
            exchange_type=(
                self.metadata[symbol][
                    "exchange_type"
                ]
            ),
            tokens=[token],
            mode=int(mode),
        )

    def start(
        self,
        symbol: str,
        correlation_id: str | None = None,
        mode: int = 1,
    ) -> None:
        """
        Start one registered IPO runner.
        """

        normalized = self._normalize_symbol(
            symbol
        )

        runner = self.runners.get(
            normalized
        )

        if runner is None:
            raise ValueError(
                f"IPO runner is not registered: "
                f"{normalized}"
            )

        start = getattr(
            runner,
            "start",
            None,
        )

        if callable(start):
            start(
                correlation_id=correlation_id,
                mode=int(mode),
            )

        self.session_closed = False

    def stop(
        self,
        symbol: str,
    ) -> None:
        """
        Stop one registered IPO runner.
        """

        normalized = self._normalize_symbol(
            symbol
        )

        runner = self.runners.get(
            normalized
        )

        if runner is None:
            raise ValueError(
                f"IPO runner is not registered: "
                f"{normalized}"
            )

        stop = getattr(
            runner,
            "stop",
            None,
        )

        if callable(stop):
            stop()

    def start_all(
        self,
        mode: int = 1,
    ) -> None:
        """
        Start all registered IPO runners.
        """

        if self.websocket is not None:
            connect = getattr(
                self.websocket,
                "connect",
                None,
            )

            if callable(connect):
                connect()

        for symbol, runner in self.runners.items():
            start = getattr(
                runner,
                "start",
                None,
            )

            if callable(start):
                start(
                    correlation_id=(
                        f"IPO_PAPER_{symbol}"
                    ),
                    mode=int(mode),
                )

        self.session_closed = False

    def stop_all(self) -> None:
        """
        Stop all registered IPO runners.
        """

        for runner in self.runners.values():
            stop = getattr(
                runner,
                "stop",
                None,
            )

            if callable(stop):
                stop()

        if self.websocket is not None:
            close = getattr(
                self.websocket,
                "close",
                None,
            )

            if callable(close):
                close()

    # ------------------------------------------------------------------
    # Candle processing
    # ------------------------------------------------------------------

    def process_candle(
        self,
        symbol: str,
        candle: Any,
    ) -> dict[str, Any] | None:
        """
        Process a candle for a specific IPO.

        This method is useful for tests and direct integrations
        that do not route candles through the WebSocket callback.
        """

        normalized_symbol = (
            self._normalize_symbol(symbol)
        )

        if normalized_symbol not in self.runners:
            raise ValueError(
                f"IPO runner is not registered: "
                f"{normalized_symbol}"
            )

        normalized = self._normalize_candle(
            candle
        )

        if normalized is None:
            return None

        normalized["symbol"] = (
            normalized_symbol
        )

        return self.on_candle(
            normalized
        )

    # ------------------------------------------------------------------
    # State / statistics
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """
        Return complete session state.
        """

        ipos: dict[str, Any] = {}

        for symbol, runner in self.runners.items():
            get_state = getattr(
                runner,
                "get_state",
                None,
            )

            if callable(get_state):
                runner_state = get_state()
            else:
                runner_state = {}

            ipos[symbol] = {
                "metadata": self.metadata.get(
                    symbol,
                    {},
                ),
                "state": runner_state,
            }

        return {
            "count": len(
                self.runners
            ),
            "session_closed": (
                self.session_closed
            ),
            "last_candle": self.last_candle,
            "last_result": self.last_result,
            "ipos": ipos,
        }

    def get_orders(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return combined paper orders from all IPOs.
        """

        orders: list[dict[str, Any]] = []

        for runner in self.runners.values():
            get_orders = getattr(
                runner,
                "get_orders",
                None,
            )

            if callable(get_orders):
                result = get_orders()

                if result:
                    orders.extend(
                        result
                    )

        return orders

    def get_realized_pnl(
        self,
    ) -> float:
        """
        Return combined realized paper P&L.
        """

        total = 0.0

        for runner in self.runners.values():
            get_pnl = getattr(
                runner,
                "get_realized_pnl",
                None,
            )

            if callable(get_pnl):
                total += float(
                    get_pnl()
                )

        return total

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """
        Reset all runners and session statistics.
        """

        for runner in self.runners.values():
            reset = getattr(
                runner,
                "reset",
                None,
            )

            if callable(reset):
                reset()

        self.runners.clear()
        self.metadata.clear()

        self.last_candle = None
        self.last_result = None
        self.session_closed = False