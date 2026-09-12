from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.execution.broker import Broker


@dataclass
class PaperOrder:
    """A simulated paper-trading order."""

    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: datetime
    status: str = "FILLED"


@dataclass
class PaperPosition:
    """A simulated open long position."""

    symbol: str
    quantity: int
    average_price: float


class PaperBroker(Broker):
    """
    In-memory paper-trading broker.

    This broker never sends orders to a real exchange or broker.
    Orders are immediately treated as FILLED at the supplied price.

    Supported operations:
        - BUY
        - SELL
        - position tracking
        - average-price calculation
        - realized P&L
        - order history
        - account reset
    """

    def __init__(
        self,
        initial_cash: float = 0.0,
        slippage_pct: float = 0.0,
    ):
        if isinstance(initial_cash, bool):
            raise ValueError("initial_cash must be numeric.")

        try:
            initial_cash = float(initial_cash)
        except (TypeError, ValueError):
            raise ValueError(
                "initial_cash must be numeric."
            ) from None

        if initial_cash < 0:
            raise ValueError(
                "initial_cash cannot be negative."
            )

        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.slippage_pct = max(0.0, float(slippage_pct))

        self.orders: list[PaperOrder] = []
        self.positions: dict[str, PaperPosition] = {}
        self.realized_pnl: float = 0.0
        self._order_counter = 0

    def _next_order_id(self) -> str:
        """Generate a unique paper-order ID."""
        self._order_counter += 1
        return f"PAPER-{self._order_counter:06d}"

    @staticmethod
    def _validate_side(side: str) -> str:
        """Validate and normalize BUY/SELL."""
        if not isinstance(side, str):
            raise ValueError(
                "side must be a string."
            )

        normalized = side.strip().upper()

        if normalized not in {"BUY", "SELL"}:
            raise ValueError(
                f"Unsupported order side: {side}"
            )

        return normalized

    @staticmethod
    def _validate_quantity(quantity: int) -> int:
        """Validate order quantity."""
        if isinstance(quantity, bool) or not isinstance(
            quantity,
            int,
        ):
            raise ValueError(
                "quantity must be an integer."
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        return quantity

    @staticmethod
    def _validate_price(price: float) -> float:
        """Validate order price."""
        try:
            normalized = float(price)
        except (TypeError, ValueError):
            raise ValueError(
                "price must be numeric."
            ) from None

        if normalized <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        return normalized

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute an immediate paper order.

        BUY:
            Creates or increases a long position.

        SELL:
            Reduces an existing long position and realizes P&L.

        Returns:
            Dictionary containing the simulated order details.
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "symbol is required."
            )

        symbol = symbol.strip().upper()

        side = self._validate_side(side)
        quantity = self._validate_quantity(quantity)
        price = self._validate_price(price)

        if timestamp is None:
            timestamp = datetime.now()

        if not isinstance(timestamp, datetime):
            raise ValueError(
                "timestamp must be a datetime."
            )

        if self.slippage_pct > 0:
            if side == "BUY":
                fill_price = round(price * (1.0 + self.slippage_pct), 2)
            else:
                fill_price = round(price * (1.0 - self.slippage_pct), 2)
        else:
            fill_price = price

        if side == "BUY":
            self._buy(
                symbol=symbol,
                quantity=quantity,
                price=fill_price,
            )
        else:
            self._sell(
                symbol=symbol,
                quantity=quantity,
                price=fill_price,
            )

        order = PaperOrder(
            order_id=self._next_order_id(),
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=fill_price,
            timestamp=timestamp,
        )

        self.orders.append(order)

        return self._order_to_dict(order)

    def _buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
    ) -> None:
        """Create or increase a long position."""

        existing = self.positions.get(symbol)

        if existing is None:
            self.positions[symbol] = PaperPosition(
                symbol=symbol,
                quantity=quantity,
                average_price=price,
            )
            return

        total_quantity = (
            existing.quantity + quantity
        )

        total_value = (
            existing.quantity
            * existing.average_price
            + quantity * price
        )

        existing.quantity = total_quantity
        existing.average_price = (
            total_value / total_quantity
        )

    def _sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
    ) -> None:
        """Reduce a long position and realize P&L."""

        existing = self.positions.get(symbol)

        if existing is None:
            raise ValueError(
                f"No open position for {symbol}."
            )

        if quantity > existing.quantity:
            raise ValueError(
                f"Cannot sell {quantity} shares of "
                f"{symbol}; only {existing.quantity} "
                f"are available."
            )

        pnl = (
            price - existing.average_price
        ) * quantity

        self.realized_pnl += pnl

        remaining_quantity = (
            existing.quantity - quantity
        )

        if remaining_quantity == 0:
            del self.positions[symbol]
        else:
            existing.quantity = remaining_quantity

    @staticmethod
    def _order_to_dict(
        order: PaperOrder,
    ) -> dict[str, Any]:
        """Convert an order object into a dictionary."""

        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
            "timestamp": order.timestamp,
            "status": order.status,
        }

    @staticmethod
    def _position_to_dict(
        position: PaperPosition,
    ) -> dict[str, Any]:
        """Convert a position object into a dictionary."""

        return {
            "symbol": position.symbol,
            "quantity": position.quantity,
            "average_price": position.average_price,
        }

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the current open position for a symbol."""

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "symbol is required."
            )

        symbol = symbol.strip().upper()

        position = self.positions.get(symbol)

        if position is None:
            return None

        return self._position_to_dict(position)

    def get_orders(self) -> list[dict[str, Any]]:
        """Return all paper orders in execution order."""

        return [
            self._order_to_dict(order)
            for order in self.orders
        ]

    def get_realized_pnl(self) -> float:
        """Return total realized P&L."""

        return self.realized_pnl

    def reset(self) -> None:
        """Reset all paper orders, positions, and P&L."""

        self.orders.clear()
        self.positions.clear()
        self.realized_pnl = 0.0
        self._order_counter = 0