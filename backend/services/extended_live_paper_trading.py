from __future__ import annotations

from datetime import datetime
from typing import Any


class ExtendedLivePaperTrading:
    """
    Extended live-style paper-trading runner.

    Responsibilities:
        - Accept completed market candles.
        - Ignore candles before market open.
        - Process candles during regular market hours.
        - Force paper exit at/after market close.
        - Track processed candles and decisions.
        - Expose paper-trading state and reports.

    PAPER TRADING ONLY.
    This class never places real broker orders directly.
    """

    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15

    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30

    def __init__(
        self,
        session_service: Any,
    ):
        if session_service is None:
            raise ValueError(
                "session_service is required."
            )

        # Do NOT use isinstance(IPOLiveSessionService).
        #
        # The production service and the test FakeSessionService
        # expose the required behaviour without needing inheritance.
        self.session_service = session_service

        self.candles_processed = 0

        self.results: list[
            dict[str, Any]
        ] = []

    # ============================================================
    # VALIDATION
    # ============================================================

    @staticmethod
    def _get_symbol(
        candle: dict[str, Any],
    ) -> str:
        symbol = candle.get("symbol")

        if not isinstance(symbol, str):
            raise ValueError(
                "candle symbol is required."
            )

        symbol = symbol.strip()

        if not symbol:
            raise ValueError(
                "candle symbol is required."
            )

        return symbol.upper()

    @staticmethod
    def _get_timestamp(
        candle: dict[str, Any],
    ) -> datetime:
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

        return timestamp

    @staticmethod
    def _get_close_price(
        candle: dict[str, Any],
    ) -> float:
        price = candle.get("close")

        if price is None:
            price = candle.get(
                "close_price"
            )

        if price is None:
            raise ValueError(
                "candle close price is required."
            )

        price = float(price)

        if price <= 0:
            raise ValueError(
                "candle close price must be greater than zero."
            )

        return price

    # ============================================================
    # MARKET SESSION
    # ============================================================

    @classmethod
    def _is_before_market_open(
        cls,
        timestamp: datetime,
    ) -> bool:
        return (
            timestamp.hour,
            timestamp.minute,
            timestamp.second,
        ) < (
            cls.MARKET_OPEN_HOUR,
            cls.MARKET_OPEN_MINUTE,
            0,
        )

    @classmethod
    def _is_after_market_close(
        cls,
        timestamp: datetime,
    ) -> bool:
        return (
            timestamp.hour,
            timestamp.minute,
            timestamp.second,
        ) >= (
            cls.MARKET_CLOSE_HOUR,
            cls.MARKET_CLOSE_MINUTE,
            0,
        )

    @classmethod
    def _is_market_open(
        cls,
        timestamp: datetime,
    ) -> bool:
        return not (
            cls._is_before_market_open(
                timestamp
            )
            or
            cls._is_after_market_close(
                timestamp
            )
        )

    # ============================================================
    # NORMAL CANDLE PROCESSING
    # ============================================================

    def _process_normal_candle(
        self,
        symbol: str,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Send a valid market candle through the session service.

        Preferred interface:

            session_service.process_candle(
                symbol,
                candle,
            )

        A fallback to the registered runner is provided for
        production compatibility if the session service itself
        does not expose process_candle().
        """

        process_candle = getattr(
            self.session_service,
            "process_candle",
            None,
        )

        if callable(process_candle):
            return process_candle(
                symbol,
                candle,
            )

        # --------------------------------------------------------
        # Production fallback
        # --------------------------------------------------------

        runners = getattr(
            self.session_service,
            "runners",
            None,
        )

        if not isinstance(
            runners,
            dict,
        ):
            raise AttributeError(
                "session_service must expose "
                "process_candle() or runners."
            )

        runner = runners.get(symbol)

        if runner is None:
            raise ValueError(
                f"IPO runner is not registered: {symbol}"
            )

        runner_process = getattr(
            runner,
            "process_candle",
            None,
        )

        if callable(runner_process):
            return runner_process(
                candle
            )

        # Last production compatibility option.
        on_candle = getattr(
            runner,
            "_on_candle",
            None,
        )

        if callable(on_candle):
            return on_candle(
                candle
            )

        raise AttributeError(
            "Registered IPO runner must expose "
            "process_candle()."
        )

    # ============================================================
    # EOD PROCESSING
    # ============================================================

    def _force_eod_exit(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
    ) -> dict[str, Any] | None:
        """
        Force an EOD paper exit through the session service.
        """

        force_exit = getattr(
            self.session_service,
            "force_exit",
            None,
        )

        if not callable(force_exit):
            raise AttributeError(
                "session_service must expose "
                "force_exit()."
            )

        return force_exit(
            symbol,
            price,
            timestamp,
        )

    # ============================================================
    # PROCESS ONE CANDLE
    # ============================================================

    def process_candle(
        self,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Process one completed candle.

        Rules:

            Before 09:15
                -> ignore

            09:15 through 15:29
                -> process normally

            15:30 or later
                -> force EOD paper exit

        Ignored candles are NOT counted.
        """

        if not isinstance(
            candle,
            dict,
        ):
            raise ValueError(
                "candle must be a dictionary."
            )

        symbol = self._get_symbol(
            candle
        )

        timestamp = self._get_timestamp(
            candle
        )

        # --------------------------------------------------------
        # BEFORE MARKET OPEN
        # --------------------------------------------------------

        if self._is_before_market_open(
            timestamp
        ):
            return None

        # --------------------------------------------------------
        # MARKET CLOSE / EOD
        # --------------------------------------------------------

        if self._is_after_market_close(
            timestamp
        ):
            price = self._get_close_price(
                candle
            )

            result = self._force_eod_exit(
                symbol,
                price,
                timestamp,
            )

            if isinstance(
                result,
                dict,
            ):
                self.results.append(
                    dict(result)
                )

            return result

        # --------------------------------------------------------
        # NORMAL MARKET HOURS
        # --------------------------------------------------------

        if not self._is_market_open(
            timestamp
        ):
            return None

        # Count only valid market candles.
        self.candles_processed += 1

        result = self._process_normal_candle(
            symbol,
            candle,
        )

        if isinstance(
            result,
            dict,
        ):
            self.results.append(
                dict(result)
            )

        return result

    # ============================================================
    # PROCESS MULTIPLE CANDLES
    # ============================================================

    def run(
        self,
        candles: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:
        """
        Process multiple candles.
        """

        if not isinstance(
            candles,
            list,
        ):
            raise ValueError(
                "candles must be a list."
            )

        for candle in candles:
            self.process_candle(
                candle
            )

        return self.get_report()

    # ============================================================
    # STATE
    # ============================================================

    def get_state(
        self,
    ) -> dict[str, Any]:
        """
        Return the underlying session state.
        """

        return self.session_service.get_state()

    # ============================================================
    # REPORT
    # ============================================================

    def get_report(
        self,
    ) -> dict[str, Any]:
        """
        Return extended paper-trading report.
        """

        state = self.session_service.get_state()

        return {
            "candles_processed": (
                self.candles_processed
            ),
            "results_count": len(
                self.results
            ),
            "results": list(
                self.results
            ),
            "running": state.get(
                "running",
                False,
            ),
            "session_closed": state.get(
                "session_closed",
                False,
            ),
            "ipos": state.get(
                "ipos",
                {},
            ),
        }

    # ============================================================
    # PAPER ORDERS
    # ============================================================

    def get_orders(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all paper orders.
        """

        get_orders = getattr(
            self.session_service,
            "get_orders",
            None,
        )

        if not callable(
            get_orders
        ):
            return []

        return list(
            get_orders()
        )

    # ============================================================
    # REALIZED P&L
    # ============================================================

    def get_realized_pnl(
        self,
    ) -> float:
        """
        Return total realized paper P&L.
        """

        get_realized_pnl = getattr(
            self.session_service,
            "get_realized_pnl",
            None,
        )

        if not callable(
            get_realized_pnl
        ):
            return 0.0

        return float(
            get_realized_pnl()
        )

    # ============================================================
    # RESET
    # ============================================================

    def reset(
        self,
    ) -> None:
        """
        Reset the complete paper-trading session.
        """

        reset = getattr(
            self.session_service,
            "reset",
            None,
        )

        if not callable(
            reset
        ):
            raise AttributeError(
                "session_service must expose "
                "reset()."
            )

        reset()

        self.candles_processed = 0

        self.results.clear()