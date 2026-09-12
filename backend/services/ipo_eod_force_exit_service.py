from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.services.market_session_service import (
    MarketSessionService,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)


class IPOEODForceExitService:
    """
    Handles end-of-day safety for IPO paper trading.

    Responsibilities:
        - Detect market close.
        - Prevent further entry after market close.
        - Exit an open paper position at the supplied price.
        - Preserve paper-only execution.

    This service NEVER places a real broker order.
    """

    def __init__(
        self,
        execution_service: IPOLivePaperExecutionService,
        session_service: MarketSessionService | None = None,
    ):
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

        self.execution_service = execution_service

        self.session_service = (
            session_service
            if session_service is not None
            else MarketSessionService()
        )

        self.session_closed = False
        self.last_result: dict[str, Any] | None = None

    def is_market_closed(
        self,
        timestamp: datetime,
    ) -> bool:
        return self.session_service.is_after_market_close(
            timestamp
        )

    def should_accept_entry(
        self,
        timestamp: datetime,
    ) -> bool:
        """
        Return True only while the regular market session
        is open.
        """

        if self.session_closed:
            return False

        return self.session_service.is_market_open(
            timestamp
        )

    def force_exit(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
    ) -> dict[str, Any]:
        """
        Force-close an open paper position.

        If no position exists, no order is created.
        """

        if not isinstance(
            symbol,
            str,
        ) or not symbol.strip():
            raise ValueError(
                "symbol is required."
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

        symbol = symbol.strip().upper()

        position = (
            self.execution_service.get_position(
                symbol
            )
        )

        if position is None:
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

            self.session_closed = True
            self.last_result = result

            return result

        quantity = position.get(
            "quantity"
        )

        if quantity is None:
            raise ValueError(
                "Open position has no quantity."
            )

        quantity = int(quantity)

        if quantity <= 0:
            raise ValueError(
                "Open position quantity must "
                "be greater than zero."
            )

        result = (
            self.execution_service.execute_decision(
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
        )

        result["action"] = "EOD_EXIT"
        result["eod_force_exit"] = True

        self.session_closed = True
        self.last_result = result

        return result

    def close_session(
        self,
        timestamp: datetime,
    ) -> dict[str, Any]:
        """
        Mark the session closed without creating an order.
        """

        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "timestamp must be a datetime."
            )

        self.session_closed = True

        result = {
            "action": "SESSION_CLOSED",
            "executed": False,
            "symbol": None,
            "quantity": 0,
            "price": None,
            "timestamp": timestamp,
            "order": None,
            "reason": (
                "Trading session closed."
            ),
        }

        self.last_result = result

        return result

    def reset(self) -> None:
        """
        Re-enable the service for a new trading session.
        """

        self.session_closed = False
        self.last_result = None