from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.services.angel_one_ipo_live_paper_runner import (
    AngelOneIPOLivePaperRunner,
)
from backend.services.ipo_eod_force_exit_service import (
    IPOEODForceExitService,
)
from backend.services.market_session_service import (
    MarketSessionService,
)


class ExtendedIPOLivePaperRunner:
    """
    Extended live IPO paper-trading orchestrator.

    Responsibilities:
        - Manage multiple IPO runners.
        - Enforce NSE market-session boundaries.
        - Ignore pre-open candles.
        - Process candles during regular market hours.
        - Force-exit open paper positions at EOD.
        - Expose session and runner state.
        - Reset the complete session.

    SAFETY:
        This class is PAPER TRADING ONLY.
        It never places real broker orders.
    """

    def __init__(
        self,
        runners: dict[str, AngelOneIPOLivePaperRunner],
        session_service: MarketSessionService | None = None,
        eod_service: IPOEODForceExitService | None = None,
    ):
        if not isinstance(runners, dict):
            raise TypeError(
                "runners must be a dictionary."
            )

        if not runners:
            raise ValueError(
                "At least one IPO runner is required."
            )

        for symbol, runner in runners.items():
            if not isinstance(symbol, str):
                raise TypeError(
                    "Runner symbols must be strings."
                )

            if not symbol.strip():
                raise ValueError(
                    "Runner symbols cannot be empty."
                )

            if not isinstance(
                runner,
                AngelOneIPOLivePaperRunner,
            ):
                raise TypeError(
                    "All runners must be "
                    "AngelOneIPOLivePaperRunner instances."
                )

        self.runners = {
            symbol.strip().upper(): runner
            for symbol, runner in runners.items()
        }

        self.session_service = (
            session_service
            if session_service is not None
            else MarketSessionService()
        )

        # EOD service can only operate on one execution service,
        # therefore it is optional at construction time.
        #
        # Existing integrations/tests may attach it after creation.
        self.eod_service = eod_service

        self.running = False
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None

        self.candles_processed = 0
        self.decisions_processed = 0

        self.last_candle: dict[str, Any] | None = None
        self.last_result: dict[str, Any] | None = None

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================

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
    def _get_timestamp(
        candle: Any,
    ) -> datetime:
        if isinstance(candle, dict):
            timestamp = candle.get(
                "timestamp"
            )
        else:
            timestamp = getattr(
                candle,
                "timestamp",
                None,
            )

        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "candle timestamp must be a datetime."
            )

        return timestamp

    def _get_runner(
        self,
        symbol: str,
    ) -> AngelOneIPOLivePaperRunner:
        normalized = self._normalize_symbol(
            symbol
        )

        runner = self.runners.get(
            normalized
        )

        if runner is None:
            raise KeyError(
                f"No runner registered for {normalized}."
            )

        return runner

    def _get_execution_service(
        self,
        runner: AngelOneIPOLivePaperRunner,
    ) -> Any:
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

        return execution_service

    # ================================================================
    # START / STOP
    # ================================================================

    def start(self) -> None:
        """
        Start all configured IPO paper runners.
        """

        if self.running:
            return

        self.started_at = datetime.now()
        self.stopped_at = None

        for runner in self.runners.values():
            start = getattr(
                runner,
                "start",
                None,
            )

            if callable(start):
                start()

        self.running = True

    def stop(self) -> None:
        """
        Stop all configured IPO paper runners.
        """

        for runner in self.runners.values():
            stop = getattr(
                runner,
                "stop",
                None,
            )

            if callable(stop):
                stop()

        self.running = False
        self.stopped_at = datetime.now()

    # ================================================================
    # CANDLE PROCESSING
    # ================================================================

    def process_candle(
        self,
        symbol: str,
        candle: Any,
    ) -> dict[str, Any] | None:
        """
        Process one externally supplied candle.

        Only candles inside the regular market session are
        passed to the underlying IPO runner.

        Pre-open candles and the market-close boundary are ignored.

        EOD force-exit is NOT automatically triggered here.
        It is performed explicitly through force_eod_exit().
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "symbol is required."
            )

        if not isinstance(candle, dict):
            raise TypeError(
                "candle must be a dictionary."
            )

        normalized_symbol = (
            symbol.strip().upper()
        )

        runner = self.runners.get(
            normalized_symbol
        )

        if runner is None:
            raise KeyError(
                f"No runner registered for "
                f"{normalized_symbol}."
            )

        timestamp = candle.get(
            "timestamp"
        )

        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "candle timestamp must be a datetime."
            )

        # ---------------------------------------------------------
        # MARKET SESSION FILTER
        # ---------------------------------------------------------
        #
        # The regular IPO trading session is:
        #
        #     09:15 <= time < 15:30
        #
        # Therefore:
        #
        #     09:00 -> ignored
        #     09:14 -> ignored
        #     09:15 -> processed
        #     15:29 -> processed
        #     15:30 -> ignored
        #     15:31 -> ignored
        #
        # ---------------------------------------------------------

        session_service = getattr(
            self,
            "session_service",
            None,
        )

        if session_service is not None:
            if not session_service.is_market_open(
                timestamp
            ):
                return None

        # ---------------------------------------------------------
        # PROCESS VALID MARKET CANDLE
        # ---------------------------------------------------------

        self.candles_processed += 1

        before_result = runner.last_result

        runner._on_candle(
            candle
        )

        after_result = runner.last_result

        if after_result is not before_result:
            self.decisions_processed += 1

        return after_result

    # ================================================================
    # CANDLE HELPERS
    # ================================================================

    @staticmethod
    def _get_candle_close_price(
        candle: Any,
    ) -> float:
        if isinstance(candle, dict):
            value = candle.get(
                "close_price"
            )

            if value is None:
                value = candle.get(
                    "close"
                )
        else:
            value = getattr(
                candle,
                "close_price",
                None,
            )

            if value is None:
                value = getattr(
                    candle,
                    "close",
                    None,
                )

        if value is None:
            raise ValueError(
                "candle close price is required."
            )

        value = float(value)

        if value <= 0:
            raise ValueError(
                "candle close price must be greater than zero."
            )

        return value

    @staticmethod
    def _normalize_candle(
        symbol: str,
        candle: Any,
    ) -> dict[str, Any]:
        if isinstance(candle, dict):
            timestamp = candle.get(
                "timestamp"
            )

            open_price = candle.get(
                "open_price",
                candle.get(
                    "open"
                ),
            )

            high_price = candle.get(
                "high_price",
                candle.get(
                    "high"
                ),
            )

            low_price = candle.get(
                "low_price",
                candle.get(
                    "low"
                ),
            )

            close_price = candle.get(
                "close_price",
                candle.get(
                    "close"
                ),
            )

            volume = candle.get(
                "volume"
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

        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "candle timestamp must be a datetime."
            )

        if (
            open_price is None
            or high_price is None
            or low_price is None
            or close_price is None
        ):
            raise ValueError(
                "candle OHLC prices are required."
            )

        result = {
            "symbol": symbol,
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

        return result

    # ================================================================
    # EOD FORCE EXIT
    # ================================================================

    def force_eod_exit(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
    ) -> dict[str, Any]:
        """
        Force-close an open paper position.

        No position:
            no order is created.

        Open position:
            EXIT paper order is generated.

        This never places a real broker order.
        """

        normalized_symbol = self._normalize_symbol(
            symbol
        )

        price = float(price)

        if price <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "timestamp must be a datetime."
            )

        runner = self._get_runner(
            normalized_symbol
        )

        execution_service = (
            self._get_execution_service(
                runner
            )
        )

        # ------------------------------------------------------------
        # Prefer configured EOD service
        # ------------------------------------------------------------

        if self.eod_service is not None:
            result = self.eod_service.force_exit(
                normalized_symbol,
                price,
                timestamp,
            )

            self.last_result = result

            return result

        # ------------------------------------------------------------
        # Fallback directly to runner execution service
        # ------------------------------------------------------------

        if execution_service is None:
            raise RuntimeError(
                "Runner has no paper execution service."
            )

        get_position = getattr(
            execution_service,
            "get_position",
            None,
        )

        if not callable(get_position):
            raise AttributeError(
                "Execution service does not expose "
                "get_position()."
            )

        position = get_position(
            normalized_symbol
        )

        if position is None:
            result = {
                "action": "EOD_EXIT",
                "executed": False,
                "symbol": normalized_symbol,
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

        quantity = int(
            position.get(
                "quantity",
                0,
            )
        )

        if quantity <= 0:
            result = {
                "action": "EOD_EXIT",
                "executed": False,
                "symbol": normalized_symbol,
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

        execute_decision = getattr(
            execution_service,
            "execute_decision",
            None,
        )

        if not callable(execute_decision):
            raise AttributeError(
                "Execution service does not expose "
                "execute_decision()."
            )

        result = execute_decision(
            {
                "action": "EXIT",
                "symbol": normalized_symbol,
                "quantity": quantity,
                "price": price,
                "reason": (
                    "End-of-day force exit."
                ),
            },
            timestamp=timestamp,
        )

        if not isinstance(
            result,
            dict,
        ):
            result = {
                "action": "EOD_EXIT",
                "executed": True,
                "symbol": normalized_symbol,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp,
                "order": result,
            }

        result["action"] = "EOD_EXIT"
        result["eod_force_exit"] = True

        self.last_result = result

        return result

    # ================================================================
    # FLUSH
    # ================================================================

    def flush(self) -> dict[str, Any]:
        """
        Flush all configured runners.
        """

        results: dict[str, Any] = {}

        for symbol, runner in self.runners.items():
            flush = getattr(
                runner,
                "flush",
                None,
            )

            if callable(flush):
                results[symbol] = flush()

        return results

    # ================================================================
    # ORDERS
    # ================================================================

    def get_orders(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all paper orders.
        """

        orders: list[dict[str, Any]] = []

        for symbol, runner in self.runners.items():
            get_orders = getattr(
                runner,
                "get_orders",
                None,
            )

            if not callable(get_orders):
                continue

            runner_orders = get_orders()

            if not runner_orders:
                continue

            for order in runner_orders:
                item = dict(order)

                if "symbol" not in item:
                    item["symbol"] = symbol

                orders.append(item)

        return orders

    # ================================================================
    # POSITIONS
    # ================================================================

    def get_positions(
        self,
    ) -> dict[str, dict[str, Any] | None]:
        """
        Return current paper position for every IPO.
        """

        positions: dict[
            str,
            dict[str, Any] | None,
        ] = {}

        for symbol, runner in self.runners.items():
            get_position = getattr(
                runner,
                "get_position",
                None,
            )

            if callable(get_position):
                positions[symbol] = (
                    get_position()
                )
                continue

            execution_service = (
                self._get_execution_service(
                    runner
                )
            )

            if execution_service is not None:
                get_position = getattr(
                    execution_service,
                    "get_position",
                    None,
                )

                if callable(get_position):
                    positions[symbol] = (
                        get_position(symbol)
                    )
                    continue

            positions[symbol] = None

        return positions

    # ================================================================
    # P&L
    # ================================================================

    def get_realized_pnl(self) -> float:
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

    # ================================================================
    # STATE
    # ================================================================

    def get_state(
        self,
    ) -> dict[str, Any]:
        """
        Return complete session state.

        Includes:

            session
            ipos
            candles_processed
            decisions_processed
            last_candle
            last_result
        """

        session_state = (
            self.session_service.get_session_state(
                self.last_candle["timestamp"]
                if self.last_candle is not None
                else datetime.now(
                    self.session_service.IST
                )
            )
        )

        eod_session_closed = False

        if self.eod_service is not None:
            eod_session_closed = bool(
                self.eod_service.session_closed
            )

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

            ipos[symbol] = runner_state

        return {
            "running": self.running,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "candles_processed": (
                self.candles_processed
            ),
            "decisions_processed": (
                self.decisions_processed
            ),
            "last_candle": self.last_candle,
            "last_result": self.last_result,
            "session_closed": (
                self.eod_service.session_closed
                if self.eod_service is not None
                else False
            ),
            "session": {
                "state": session_state,
                "eod_session_closed": (
                    eod_session_closed
                ),
            },
            "ipos": ipos,
        }

    # ================================================================
    # REPORT
    # ================================================================

    def get_report(
        self,
    ) -> dict[str, Any]:
        """
        Return aggregate paper-trading report.
        """

        orders = self.get_orders()

        winning_trades = 0
        losing_trades = 0

        for runner in self.runners.values():
            get_state = getattr(
                runner,
                "get_state",
                None,
            )

            if not callable(get_state):
                continue

            state = get_state()

            result = state.get(
                "last_result"
            )

            if not isinstance(
                result,
                dict,
            ):
                continue

            outcome = str(
                result.get(
                    "outcome",
                    "",
                )
            ).strip().upper()

            if outcome in {
                "TARGET",
                "PROFIT",
                "WIN",
                "SUCCESS",
            }:
                winning_trades += 1

            elif outcome in {
                "STOP_LOSS",
                "LOSS",
                "LOSING",
            }:
                losing_trades += 1

        total_trades = (
            winning_trades
            + losing_trades
        )

        return {
            "running": self.running,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "ipo_count": len(
                self.runners
            ),
            "candles_processed": (
                self.candles_processed
            ),
            "decisions_processed": (
                self.decisions_processed
            ),
            "orders": orders,
            "order_count": len(
                orders
            ),
            "positions": self.get_positions(),
            "realized_pnl": (
                self.get_realized_pnl()
            ),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "session": self.get_state()[
                "session"
            ],
        }

    # ================================================================
    # RESET
    # ================================================================

    def reset(self) -> None:
        """
        Reset the complete paper-trading session.
        """

        for runner in self.runners.values():
            reset = getattr(
                runner,
                "reset",
                None,
            )

            if callable(reset):
                reset()

        if self.eod_service is not None:
            reset = getattr(
                self.eod_service,
                "reset",
                None,
            )

            if callable(reset):
                reset()

        self.running = False
        self.started_at = None
        self.stopped_at = None

        self.candles_processed = 0
        self.decisions_processed = 0

        self.last_candle = None
        self.last_result = None