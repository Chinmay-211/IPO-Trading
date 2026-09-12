from __future__ import annotations

from typing import Any


class IPOPaperPerformanceService:
    """
    Calculates performance statistics from paper-trading orders.

    This service is reporting-only.
    It does not place, modify, or cancel orders.
    """

    def __init__(self, orders: list[dict[str, Any]] | None = None):
        self.orders = list(orders or [])

    def set_orders(
        self,
        orders: list[dict[str, Any]],
    ) -> None:
        if not isinstance(orders, list):
            raise ValueError("orders must be a list.")

        self.orders = list(orders)

    def add_order(
        self,
        order: dict[str, Any],
    ) -> None:
        if not isinstance(order, dict):
            raise ValueError("order must be a dictionary.")

        self.orders.append(order)

    @staticmethod
    def _side(order: dict[str, Any]) -> str:
        return str(
            order.get("side", "")
        ).strip().upper()

    @staticmethod
    def _symbol(order: dict[str, Any]) -> str:
        return str(
            order.get("symbol", "")
        ).strip().upper()

    @staticmethod
    def _quantity(order: dict[str, Any]) -> int:
        return int(order.get("quantity", 0))

    @staticmethod
    def _price(order: dict[str, Any]) -> float:
        return float(order.get("price", 0))

    def _closed_trades(
        self,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Pair BUY orders with subsequent SELL orders.

        Supports multiple sequential trades for the same symbol.
        """

        normalized_symbol = (
            symbol.strip().upper()
            if symbol is not None
            else None
        )

        positions: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        trades: list[dict[str, Any]] = []

        for order in self.orders:
            side = self._side(order)
            current_symbol = self._symbol(order)

            if not current_symbol:
                continue

            if (
                normalized_symbol is not None
                and current_symbol != normalized_symbol
            ):
                continue

            quantity = self._quantity(order)
            price = self._price(order)

            if quantity <= 0 or price <= 0:
                continue

            if side == "BUY":
                positions.setdefault(
                    current_symbol,
                    [],
                ).append(
                    {
                        "quantity": quantity,
                        "price": price,
                        "order": order,
                    }
                )

            elif side == "SELL":
                remaining = quantity

                while (
                    remaining > 0
                    and positions.get(current_symbol)
                ):
                    entry = positions[
                        current_symbol
                    ][0]

                    matched = min(
                        remaining,
                        entry["quantity"],
                    )

                    entry_price = float(
                        entry["price"]
                    )

                    exit_price = price

                    pnl = (
                        exit_price
                        - entry_price
                    ) * matched

                    invested = (
                        entry_price * matched
                    )

                    pnl_percent = (
                        (pnl / invested) * 100
                        if invested
                        else 0.0
                    )

                    trades.append(
                        {
                            "symbol": current_symbol,
                            "quantity": matched,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "profit_loss": pnl,
                            "profit_loss_percent": pnl_percent,
                            "entry_order": entry["order"],
                            "exit_order": order,
                        }
                    )

                    entry["quantity"] -= matched
                    remaining -= matched

                    if entry["quantity"] <= 0:
                        positions[
                            current_symbol
                        ].pop(0)

        return trades

    def get_trades(
        self,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._closed_trades(symbol)

    def total_trades(
        self,
        symbol: str | None = None,
    ) -> int:
        return len(
            self._closed_trades(symbol)
        )

    def winning_trades(
        self,
        symbol: str | None = None,
    ) -> int:
        return sum(
            1
            for trade in self._closed_trades(symbol)
            if trade["profit_loss"] > 0
        )

    def losing_trades(
        self,
        symbol: str | None = None,
    ) -> int:
        return sum(
            1
            for trade in self._closed_trades(symbol)
            if trade["profit_loss"] < 0
        )

    def breakeven_trades(
        self,
        symbol: str | None = None,
    ) -> int:
        return sum(
            1
            for trade in self._closed_trades(symbol)
            if trade["profit_loss"] == 0
        )

    def win_rate(
        self,
        symbol: str | None = None,
    ) -> float:
        total = self.total_trades(symbol)

        if total == 0:
            return 0.0

        return (
            self.winning_trades(symbol)
            / total
        ) * 100

    def total_profit_loss(
        self,
        symbol: str | None = None,
    ) -> float:
        return sum(
            trade["profit_loss"]
            for trade in self._closed_trades(symbol)
        )

    def total_invested(
        self,
        symbol: str | None = None,
    ) -> float:
        return sum(
            trade["entry_price"]
            * trade["quantity"]
            for trade in self._closed_trades(symbol)
        )

    def overall_profit_loss_percent(
        self,
        symbol: str | None = None,
    ) -> float:
        invested = self.total_invested(symbol)

        if invested == 0:
            return 0.0

        return (
            self.total_profit_loss(symbol)
            / invested
        ) * 100

    def get_symbol_summary(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        symbol = symbol.strip().upper()

        return {
            "symbol": symbol,
            "total_trades": self.total_trades(symbol),
            "winning_trades": self.winning_trades(symbol),
            "losing_trades": self.losing_trades(symbol),
            "breakeven_trades": self.breakeven_trades(symbol),
            "win_rate": self.win_rate(symbol),
            "profit_loss": self.total_profit_loss(symbol),
            "profit_loss_percent": (
                self.overall_profit_loss_percent(symbol)
            ),
        }

    def get_summary(self) -> dict[str, Any]:
        symbols = sorted(
            {
                self._symbol(order)
                for order in self.orders
                if self._symbol(order)
            }
        )

        total = self.total_trades()

        return {
            "total_trades": total,
            "winning_trades": self.winning_trades(),
            "losing_trades": self.losing_trades(),
            "breakeven_trades": self.breakeven_trades(),
            "win_rate": self.win_rate(),
            "profit_loss": self.total_profit_loss(),
            "profit_loss_percent": (
                self.overall_profit_loss_percent()
            ),
            "symbols": {
                symbol: self.get_symbol_summary(symbol)
                for symbol in symbols
            },
        }

    def reset(self) -> None:
        self.orders.clear()