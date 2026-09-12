# IPO Trading System - Core Components Reference

## 1. 13-Rule Trading Strategy Implementation

### Strategy Class: IPOListingDayStrategy

**File**: `backend/strategy/ipo_listing_day_strategy.py`

```python
from dataclasses import dataclass
from datetime import datetime, time


@dataclass
class IPOListingTradeResult:
    """Result of a listing-day intraday strategy."""

    outcome: str

    entry_time: str | None
    entry_price: float | None

    stop_loss_price: float | None
    target_price: float | None

    exit_time: str | None
    exit_price: float | None

    profit_loss: float | None
    profit_loss_percent: float | None

    dip_low: float | None
    dip_percent: float | None

    confirmation_time: str | None
    confirmation_price: float | None

    reason: str


class IPOListingDayStrategy:
    """
    Listing-day IPO trading strategy.

    Rules:

    1. Observe the first 5 one-minute candles.
    2. Price must subsequently fall at least 2% below
       the listing-day opening price.
    3. Price must then recover and a 1-minute candle must
       close above the opening price.
    4. Confirmation-candle volume must be at least 1.5x
       the average volume of the preceding 5 candles.
    5. BUY at the next candle's OPEN.
    6. Stop-loss is the dip low, capped at 3% maximum
       risk below entry.
    7. Target is 2R.
    8. No new entry after 14:30.
    9. If neither stop nor target occurs, exit at 15:15.
    10. If stop and target occur in the same candle and
        tick/order data is unavailable, assume STOP first.
    """

    OBSERVATION_CANDLES = 5

    DIP_PERCENT = 2.0

    VOLUME_MULTIPLIER = 1.5

    MAX_STOP_PERCENT = 3.0

    REWARD_RISK = 2.0

    LAST_ENTRY_TIME = time(14, 30)

    FORCE_EXIT_TIME = time(15, 15)

    def run(
        self,
        candles: list[dict],
        strategy_result: str = "PASS",
    ) -> IPOListingTradeResult:
        """Execute the strategy on listing-day candles."""

        if strategy_result != "PASS":
            return self._no_trade(
                "IPO did not pass the 13-rule screening strategy."
            )

        if not candles:
            return self._not_evaluable(
                "No listing-day candles are available."
            )

        normalized = self._normalize_candles(candles)

        if len(normalized) < self.OBSERVATION_CANDLES:
            return self._not_evaluable(
                "At least 5 one-minute candles are required."
            )

        opening_price = normalized[0]["open_price"]

        if opening_price is None or opening_price <= 0:
            return self._not_evaluable(
                "Invalid listing-day opening price."
            )

        observation = normalized[:self.OBSERVATION_CANDLES]

        observation_low = min(
            candle["low_price"]
            for candle in observation
            if candle["low_price"] is not None
        )

        required_dip_price = (
            opening_price
            * (1 - self.DIP_PERCENT / 100)
        )

        dip_low = None
        dip_percent = None

        for index in range(
            self.OBSERVATION_CANDLES,
            len(normalized),
        ):

            candle = normalized[index]

            low_price = candle["low_price"]

            if (
                low_price is not None
                and low_price <= required_dip_price
            ):
                dip_low = low_price
                dip_percent = (
                    (opening_price - dip_low)
                    / opening_price
                    * 100
                )

                break

        if dip_low is None:

            return self._no_trade(
                "Required 2% dip did not occur."
            )

        dip_index = next(
            index
            for index in range(
                self.OBSERVATION_CANDLES,
                len(normalized),
            )
            if (
                normalized[index]["low_price"]
                is not None
                and normalized[index]["low_price"]
                <= required_dip_price
            )
        )

        confirmation_index = None

        for index in range(
            dip_index + 1,
            len(normalized),
        ):

            candle = normalized[index]

            timestamp = self._timestamp(candle)

            if timestamp.time() > self.LAST_ENTRY_TIME:
                break

            close_price = candle["close_price"]

            if (
                close_price is None
                or close_price <= opening_price
            ):
                continue

            previous_five = normalized[
                max(0, index - 5):index
            ]

            if len(previous_five) < 5:
                continue

            volumes = [
                c["volume"]
                for c in previous_five
                if c["volume"] is not None
            ]

            if len(volumes) < 5:
                continue

            average_volume = (
                sum(volumes)
                / len(volumes)
            )

            current_volume = candle["volume"]

            if current_volume is None:
                continue

            if current_volume < (
                average_volume
                * self.VOLUME_MULTIPLIER
            ):
                continue

            confirmation_index = index
            break

        if confirmation_index is None:

            return self._no_trade(
                "Dip occurred, but recovery and volume "
                "confirmation did not occur before 14:30."
            )

        if confirmation_index + 1 >= len(normalized):

            return self._not_evaluable(
                "No candle exists after the confirmation candle."
            )

        entry_candle = normalized[
            confirmation_index + 1
        ]

        entry_time = self._timestamp(
            entry_candle
        )

        if entry_time.time() > self.LAST_ENTRY_TIME:
            return self._no_trade(
                "BUY signal occurs after the allowed entry time."
            )

        entry_price = entry_candle["open_price"]

        if entry_price is None or entry_price <= 0:
            return self._not_evaluable(
                "Entry candle has no valid opening price."
            )

        stop_loss_price = max(
            dip_low,
            entry_price
            * (1 - self.MAX_STOP_PERCENT / 100),
        )

        risk = (
            entry_price
            - stop_loss_price
        )

        if risk <= 0:
            return self._not_evaluable(
                "Calculated stop-loss is not below entry."
            )

        target_price = (
            entry_price
            + risk * self.REWARD_RISK
        )

        confirmation_candle = normalized[
            confirmation_index
        ]

        trade_candles = normalized[
            confirmation_index + 1:
        ]

        for candle in trade_candles:

            timestamp = self._timestamp(
                candle
            )

            low_price = candle["low_price"]
            high_price = candle["high_price"]

            if timestamp.time() >= self.FORCE_EXIT_TIME:

                exit_price = (
                    candle["open_price"]
                    if candle["open_price"] is not None
                    else candle["close_price"]
                )

                if exit_price is None:
                    return self._not_evaluable(
                        "Force-exit candle has no valid price."
                    )

                return self._completed_trade(
                    outcome="TIME_EXIT",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=exit_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason=(
                        "Neither stop-loss nor target was "
                        "reached before 15:15."
                    ),
                )

            stop_hit = (
                low_price is not None
                and low_price <= stop_loss_price
            )

            target_hit = (
                high_price is not None
                and high_price >= target_price
            )

            if stop_hit and target_hit:

                return self._completed_trade(
                    outcome="STOP_LOSS",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=stop_loss_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason=(
                        "Both stop-loss and target were "
                        "touched in the same candle. "
                        "Conservative assumption: stop first."
                    ),
                )

            if stop_hit:

                return self._completed_trade(
                    outcome="STOP_LOSS",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=stop_loss_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason="Stop-loss was reached.",
                )

            if target_hit:

                return self._completed_trade(
                    outcome="TARGET",
                    entry_time=entry_time,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    target_price=target_price,
                    exit_time=timestamp,
                    exit_price=target_price,
                    dip_low=dip_low,
                    dip_percent=dip_percent,
                    confirmation_candle=confirmation_candle,
                    reason="2R target was reached.",
                )

        return self._not_evaluable(
            "Listing-day candle data ends before the "
            "strategy can determine an exit."
        )

    @staticmethod
    def _normalize_candles(candles: list[dict]) -> list[dict]:
        return sorted(
            candles,
            key=lambda candle: IPOListingDayStrategy._timestamp(candle),
        )

    @staticmethod
    def _timestamp(candle: dict) -> datetime:
        value = candle["timestamp"]
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    @staticmethod
    def _no_trade(reason: str) -> IPOListingTradeResult:
        return IPOListingTradeResult(
            outcome="NO_TRADE",
            entry_time=None,
            entry_price=None,
            stop_loss_price=None,
            target_price=None,
            exit_time=None,
            exit_price=None,
            profit_loss=None,
            profit_loss_percent=None,
            dip_low=None,
            dip_percent=None,
            confirmation_time=None,
            confirmation_price=None,
            reason=reason,
        )

    @staticmethod
    def _not_evaluable(reason: str) -> IPOListingTradeResult:
        return IPOListingTradeResult(
            outcome="NOT_EVALUABLE",
            entry_time=None,
            entry_price=None,
            stop_loss_price=None,
            target_price=None,
            exit_time=None,
            exit_price=None,
            profit_loss=None,
            profit_loss_percent=None,
            dip_low=None,
            dip_percent=None,
            confirmation_time=None,
            confirmation_price=None,
            reason=reason,
        )

    @staticmethod
    def _completed_trade(
        outcome: str,
        entry_time: datetime,
        entry_price: float,
        stop_loss_price: float,
        target_price: float,
        exit_time: datetime,
        exit_price: float,
        dip_low: float,
        dip_percent: float,
        confirmation_candle: dict,
        reason: str,
    ) -> IPOListingTradeResult:

        profit_loss = (
            exit_price - entry_price
        )

        profit_loss_percent = (
            profit_loss
            / entry_price
            * 100
        )

        confirmation_time = (
            IPOListingDayStrategy._timestamp(
                confirmation_candle
            )
        )

        return IPOListingTradeResult(
            outcome=outcome,
            entry_time=entry_time.isoformat(" "),
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
            exit_time=exit_time.isoformat(" "),
            exit_price=exit_price,
            profit_loss=profit_loss,
            profit_loss_percent=profit_loss_percent,
            dip_low=dip_low,
            dip_percent=dip_percent,
            confirmation_time=(
                confirmation_time.isoformat(" ")
            ),
            confirmation_price=(
                confirmation_candle["close_price"]
            ),
            reason=reason,
        )
```

### Key Strategy Rules Summary:

| Rule | Condition |
|------|-----------|
| 1-2 | Observe first 5 candles, 2% dip required |
| 3-4 | Price recovery + 1.5x volume confirmation |
| 5 | BUY at next candle open |
| 6 | Stop-loss = dip low (max 3% below entry) |
| 7 | Target = 2R risk/reward |
| 8 | No entry after 14:30 |
| 9 | Exit at 15:15 if no stop/target |
| 10 | Stop takes priority if both hit same candle |

---

## 2. StrategyExecutor

**File**: `backend/execution/strategy_executor.py`

```python
from datetime import datetime
from typing import Any

from backend.execution.broker import Broker


class StrategyExecutor:
    """
    Executes trading decisions through a Broker.

    The executor is broker-agnostic and works with PaperBroker
    without exposing broker-specific implementation details.
    """

    def __init__(self, broker: Broker):
        if broker is None:
            raise ValueError("broker is required.")

        self.broker = broker

    def execute_entry(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute a BUY entry."""

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

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

        try:
            normalized_price = float(price)
        except (TypeError, ValueError):
            raise ValueError(
                "price must be numeric."
            ) from None

        if normalized_price <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        if timestamp is not None and not isinstance(
            timestamp,
            datetime,
        ):
            raise ValueError(
                "timestamp must be a datetime."
            )

        order = self.broker.place_order(
            symbol=symbol.strip(),
            side="BUY",
            quantity=quantity,
            price=normalized_price,
            timestamp=timestamp,
        )

        return {
            "action": "BUY",
            "symbol": symbol.strip().upper(),
            "quantity": quantity,
            "price": normalized_price,
            "timestamp": (
                order["timestamp"]
                if timestamp is None
                else timestamp
            ),
            "order": order,
        }

    def execute_exit(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute a SELL exit."""

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

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

        try:
            normalized_price = float(price)
        except (TypeError, ValueError):
            raise ValueError(
                "price must be numeric."
            ) from None

        if normalized_price <= 0:
            raise ValueError(
                "price must be greater than zero."
            )

        if timestamp is not None and not isinstance(
            timestamp,
            datetime,
        ):
            raise ValueError(
                "timestamp must be a datetime."
            )

        order = self.broker.place_order(
            symbol=symbol.strip(),
            side="SELL",
            quantity=quantity,
            price=normalized_price,
            timestamp=timestamp,
        )

        return {
            "action": "SELL",
            "symbol": symbol.strip().upper(),
            "quantity": quantity,
            "price": normalized_price,
            "timestamp": (
                order["timestamp"]
                if timestamp is None
                else timestamp
            ),
            "order": order,
        }
```

**Design Notes**:
- Validates all inputs (symbol, quantity, price, timestamp)
- Delegates to broker (broker-agnostic)
- Returns standardized action dict
- No strategy logic (pure execution)

---

## 3. PaperTradingEngine

**File**: `backend/execution/paper_trading_engine.py`

```python
from datetime import datetime
from typing import Any

from backend.execution.strategy_executor import StrategyExecutor


class PaperTradingEngine:
    """
    Coordinates a strategy decision with paper execution.

    Flow:

        strategy decision
              ↓
        PaperTradingEngine
              ↓
        StrategyExecutor
              ↓
        PaperBroker

    This class contains orchestration only.
    It does not implement the IPO strategy itself.
    """

    def __init__(self, executor: StrategyExecutor):
        if executor is None:
            raise ValueError("executor is required.")

        self.executor = executor

    def execute(
        self,
        decision: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a strategy decision in paper trading.

        Expected decision format:

            {
                "action": "BUY",
                "symbol": "ABC",
                "quantity": 10,
                "price": 100.0
            }

        Supported actions:

            BUY
            SELL
            NO_TRADE

        NO_TRADE does not reach the broker.
        """

        if not isinstance(decision, dict):
            raise ValueError("decision must be a dictionary.")

        action = decision.get("action")

        if not isinstance(action, str):
            raise ValueError("decision action is required.")

        action = action.strip().upper()

        if action == "NO_TRADE":
            return {
                "action": "NO_TRADE",
                "executed": False,
                "order": None,
                "reason": decision.get(
                    "reason",
                    "Strategy returned NO_TRADE.",
                ),
            }

        if action not in {"BUY", "SELL"}:
            raise ValueError(
                f"Unsupported strategy action: {action}"
            )

        symbol = decision.get("symbol")
        quantity = decision.get("quantity")
        price = decision.get("price")

        if action == "BUY":
            result = self.executor.execute_entry(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )
        else:
            result = self.executor.execute_exit(
                symbol=symbol,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            )

        return {
            "action": action,
            "executed": True,
            "order": result["order"],
            "symbol": result["symbol"],
            "quantity": result["quantity"],
            "price": result["price"],
            "timestamp": result["timestamp"],
        }

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the current paper position."""

        return self.executor.broker.get_position(symbol)

    def get_orders(self) -> list[dict[str, Any]]:
        """Return all paper orders."""

        return self.executor.broker.get_orders()

    def get_realized_pnl(self) -> float:
        """Return realized paper-trading P&L."""

        return self.executor.broker.get_realized_pnl()

    def reset(self) -> None:
        """Reset the paper-trading state."""

        self.executor.broker.reset()
```

**Design Notes**:
- Filters out NO_TRADE decisions early
- Routes BUY/SELL to StrategyExecutor
- Provides introspection (positions, orders, P&L)
- Clean separation: execution vs orchestration

---

## 4. PaperBroker

**File**: `backend/execution/paper_broker.py`

```python
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

    def __init__(self, initial_cash: float = 0.0):
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

        normalized_symbol = symbol.strip().upper()
        normalized_side = self._validate_side(side)
        normalized_quantity = self._validate_quantity(quantity)
        normalized_price = self._validate_price(price)

        if timestamp is None:
            timestamp = datetime.now()

        order_id = self._next_order_id()

        if normalized_side == "BUY":
            position = self.positions.get(normalized_symbol)

            if position is None:
                self.positions[normalized_symbol] = (
                    PaperPosition(
                        symbol=normalized_symbol,
                        quantity=normalized_quantity,
                        average_price=normalized_price,
                    )
                )
            else:
                total_cost = (
                    position.average_price
                    * position.quantity
                    + normalized_price
                    * normalized_quantity
                )

                position.quantity += normalized_quantity
                position.average_price = (
                    total_cost / position.quantity
                )

        else:
            position = self.positions.get(normalized_symbol)

            if position is None:
                raise ValueError(
                    f"No open position for {normalized_symbol}."
                )

            if position.quantity < normalized_quantity:
                raise ValueError(
                    f"Cannot sell {normalized_quantity} shares; "
                    f"only {position.quantity} are available."
                )

            pnl = (
                normalized_price - position.average_price
            ) * normalized_quantity

            self.realized_pnl += pnl

            position.quantity -= normalized_quantity

            if position.quantity == 0:
                del self.positions[normalized_symbol]

        order = PaperOrder(
            order_id=order_id,
            symbol=normalized_symbol,
            side=normalized_side,
            quantity=normalized_quantity,
            price=normalized_price,
            timestamp=timestamp,
        )

        self.orders.append(order)

        return {
            "order_id": order_id,
            "symbol": normalized_symbol,
            "side": normalized_side,
            "quantity": normalized_quantity,
            "price": normalized_price,
            "timestamp": timestamp,
            "status": "FILLED",
        }

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return current position or None."""

        position = self.positions.get(
            symbol.strip().upper()
        )

        if position is None:
            return None

        return {
            "symbol": position.symbol,
            "quantity": position.quantity,
            "average_price": position.average_price,
        }

    def get_orders(self) -> list[dict[str, Any]]:
        """Return all orders."""

        return [
            {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "price": order.price,
                "timestamp": order.timestamp,
                "status": order.status,
            }
            for order in self.orders
        ]

    def get_realized_pnl(self) -> float:
        """Return realized P&L."""

        return self.realized_pnl

    def reset(self) -> None:
        """Clear all state."""

        self.orders.clear()
        self.positions.clear()
        self.realized_pnl = 0.0
        self.cash = self.initial_cash
        self._order_counter = 0
```

---

## 5. IPOTradingOrchestrator

**File**: `backend/services/ipo_trading_orchestrator.py`

```python
from datetime import datetime
from typing import Any

from backend.execution.execution_service import ExecutionService
from backend.execution.strategy_executor import StrategyExecutor


class IPOTradingOrchestrator:
    """
    Coordinates the complete IPO trading execution flow.

    Flow:
        strategy decision
            -> BUY entry
            -> monitor candles
            -> TARGET / STOP-LOSS exit

    The orchestrator is broker-agnostic. PaperBroker can be used
    safely for validation.
    """

    def __init__(
        self,
        execution_service: ExecutionService,
        strategy_executor: StrategyExecutor,
    ):
        if execution_service is None:
            raise ValueError(
                "execution_service is required."
            )

        if strategy_executor is None:
            raise ValueError(
                "strategy_executor is required."
            )

        self.execution_service = execution_service
        self.strategy_executor = strategy_executor

    def execute_trade(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
        candles: list[dict[str, Any]],
        entry_timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute one complete paper-trading strategy cycle.

        Entry is executed immediately at entry_price.

        Subsequent candles are examined in chronological order.

        TARGET:
            Exit when candle high reaches target.

        STOP-LOSS:
            Exit when candle low reaches stop loss.

        If neither occurs, the position remains open.
        """

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required.")

        if not isinstance(candles, list):
            raise ValueError("candles must be a list.")

        entry = self.strategy_executor.execute_entry(
            symbol=symbol,
            quantity=quantity,
            price=entry_price,
            timestamp=entry_timestamp,
        )

        normalized_symbol = symbol.strip().upper()

        result = {
            "status": "OPEN",
            "symbol": normalized_symbol,
            "quantity": quantity,
            "entry": entry,
            "exit": None,
            "exit_reason": None,
            "profit_loss": None,
            "profit_loss_percent": None,
        }

        for candle in candles:
            if not isinstance(candle, dict):
                continue

            timestamp = candle.get("timestamp")

            try:
                high = float(candle["high"])
                low = float(candle["low"])
            except (KeyError, TypeError, ValueError):
                continue

            exit_price = None
            exit_reason = None

            # Stop-loss takes priority if both levels occur
            # within the same candle.
            if low <= stop_loss_price:
                exit_price = float(stop_loss_price)
                exit_reason = "STOP_LOSS"

            elif high >= target_price:
                exit_price = float(target_price)
                exit_reason = "TARGET"

            if exit_price is None:
                continue

            exit_result = self.strategy_executor.execute_exit(
                symbol=normalized_symbol,
                quantity=quantity,
                price=exit_price,
                timestamp=timestamp,
            )

            pnl = (
                exit_price - float(entry_price)
            ) * quantity

            pnl_percent = (
                (
                    exit_price - float(entry_price)
                )
                / float(entry_price)
            ) * 100

            result.update(
                {
                    "status": "CLOSED",
                    "exit": exit_result,
                    "exit_reason": exit_reason,
                    "profit_loss": pnl,
                    "profit_loss_percent": pnl_percent,
                }
            )

            return result

        return result
```

**Key Flow**:
1. Entry order immediately at entry_price
2. Iterate through candles in chronological order
3. Stop-loss priority if both levels hit in same candle
4. Returns trade result with entry/exit, P&L

---

## 6. IPOPaperTradingBatch

**File**: `backend/services/ipo_paper_trading_batch.py`

```python
from typing import Any

from backend.execution.execution_service import ExecutionService
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_trading_orchestrator import (
    IPOTradingOrchestrator,
)


class IPOPaperTradingBatch:
    """
    Runs the IPO trading strategy against stored historical candles
    using the paper broker.

    This is a batch/integration layer only.
    Strategy rules remain outside this class.
    """

    def __init__(
        self,
        orchestrator: IPOTradingOrchestrator,
    ):
        if orchestrator is None:
            raise ValueError(
                "orchestrator is required."
            )

        self.orchestrator = orchestrator

    def run_one(
        self,
        ipo: dict[str, Any],
        candles: list[dict[str, Any]],
        quantity: int,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
    ) -> dict[str, Any]:
        """
        Run paper trading for one IPO using supplied candles.
        """

        if not isinstance(ipo, dict):
            raise ValueError("ipo must be a dictionary.")

        symbol = ipo.get("symbol")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(
                "IPO trading symbol is required."
            )

        listing_date = ipo.get("listing_date")

        if not listing_date:
            raise ValueError(
                "IPO listing_date is required."
            )

        result = self.orchestrator.execute_trade(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            candles=candles,
        )

        return {
            "ipo_id": ipo.get("id"),
            "company_name": ipo.get("company_name"),
            "symbol": symbol.strip().upper(),
            "listing_date": listing_date,
            "status": result["status"],
            "entry": result["entry"],
            "exit": result["exit"],
            "exit_reason": result["exit_reason"],
            "profit_loss": result["profit_loss"],
            "profit_loss_percent": result[
                "profit_loss_percent"
            ],
        }

    def run_batch(
        self,
        trades: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Run multiple IPO paper trades.

        Each item must contain:

            ipo
            candles
            quantity
            entry_price
            target_price
            stop_loss_price
        """

        if not isinstance(trades, list):
            raise ValueError(
                "trades must be a list."
            )

        results = []

        for trade in trades:
            if not isinstance(trade, dict):
                raise ValueError(
                    "Each trade must be a dictionary."
                )

            result = self.run_one(
                ipo=trade["ipo"],
                candles=trade["candles"],
                quantity=trade["quantity"],
                entry_price=trade["entry_price"],
                target_price=trade["target_price"],
                stop_loss_price=trade["stop_loss_price"],
            )

            results.append(result)

        return results
```

**Usage Example**:
```python
batch = IPOPaperTradingBatch(orchestrator)

# Single IPO
result = batch.run_one(
    ipo={
        "id": 301,
        "company_name": "Test IPO",
        "symbol": "TESTIPO",
        "listing_date": "2026-08-24"
    },
    candles=[...],
    quantity=10,
    entry_price=100,
    target_price=110,
    stop_loss_price=95
)

# Batch
results = batch.run_batch([
    {
        "ipo": {...},
        "candles": [...],
        "quantity": 10,
        ...
    },
    ...
])
```

---

## 7. LivePaperTradingService

**File**: `backend/services/live_paper_trading_service.py`

```python
from datetime import datetime
from typing import Any

from backend.execution.strategy_executor import StrategyExecutor


class LivePaperTradingService:
    """
    Coordinates live market candles with paper execution.

    This service NEVER sends real orders.
    It only uses the configured StrategyExecutor,
    which can be backed by PaperBroker.
    """

    def __init__(
        self,
        strategy_executor: StrategyExecutor,
    ):
        if strategy_executor is None:
            raise ValueError(
                "strategy_executor is required."
            )

        self.strategy_executor = strategy_executor

    def enter(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a paper BUY entry.
        """

        return self.strategy_executor.execute_entry(
            symbol=symbol,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
        )

    def exit(
        self,
        symbol: str,
        quantity: int,
        price: float,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Execute a paper SELL exit.
        """

        return self.strategy_executor.execute_exit(
            symbol=symbol,
            quantity=quantity,
            price=price,
            timestamp=timestamp,
        )

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the current paper position."""

        return self.strategy_executor.broker.get_position(
            symbol
        )

    def get_orders(self) -> list[dict[str, Any]]:
        """Return paper order history."""

        return self.strategy_executor.broker.get_orders()

    def get_realized_pnl(self) -> float:
        """Return realized paper P&L."""

        return (
            self.strategy_executor
            .broker
            .get_realized_pnl()
        )

    def reset(self) -> None:
        """Reset paper-trading state."""

        self.strategy_executor.broker.reset()
```

**Design Notes**:
- Thin wrapper around StrategyExecutor
- Clean interface for live trading decisions
- Always paper-only (no real order risk)
- Direct entry/exit methods for live signals

---

## 8. CandleRepository

**File**: `backend/storage/candle_repository.py`

```python
from backend.models.candle import Candle
from backend.storage.database import get_connection


class CandleRepository:
    """Database operations for intraday candle data."""

    def add(self, candle: Candle) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO candles (
                    symbol,
                    timestamp,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    interval,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candle.symbol,
                    candle.timestamp.isoformat(),
                    candle.open_price,
                    candle.high_price,
                    candle.low_price,
                    candle.close_price,
                    candle.volume,
                    candle.interval,
                    candle.source,
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_for_symbol(self, symbol: str) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM candles
                WHERE symbol = ?
                ORDER BY timestamp
                """,
                (symbol,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def count(self) -> int:
        connection = get_connection()

        try:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM candles"
            ).fetchone()

            return row["count"]

        finally:
            connection.close()
```

**Key Operations**:
- `add()`: Insert/update candle (INSERT OR IGNORE)
- `get_for_symbol()`: Retrieve sorted candles by timestamp
- `count()`: Total candles in database

**Important Note**: `INSERT OR IGNORE` prevents duplicate timestamps for same symbol-interval pair.

---

## 9. Angel One WebSocket Test

**File**: `backend/tests/test_angel_one_websocket.py`

```python
import os
import time
import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

import pyotp

from dotenv import load_dotenv
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2


load_dotenv()


def main():
    api_key = os.getenv("ANGEL_API_KEY")
    client_id = os.getenv("ANGEL_CLIENT_ID")
    pin = os.getenv("ANGEL_PIN")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")

    # Authenticate
    totp = pyotp.TOTP(totp_secret).now()

    smart_api = SmartConnect(api_key=api_key)

    login_response = smart_api.generateSession(
        client_id,
        pin,
        totp
    )

    if not login_response.get("status"):
        raise RuntimeError(
            "Angel One login failed. Check provider status and "
            "account configuration."
        )

    auth_token = login_response["data"]["jwtToken"]
    feed_token = login_response["data"]["feedToken"]

    print("Angel One authentication: SUCCESS")
    print("Starting WebSocket...")

    correlation_id = "ipo_test"
    mode = 1  # LTP

    sws = SmartWebSocketV2(
        auth_token,
        api_key,
        client_id,
        feed_token
    )

    def on_data(wsapp, message):
        print("\nLIVE MARKET DATA:")
        print(message)

    def on_open(wsapp):
        print("WebSocket connected: SUCCESS")

        # NIFTY 50
        token_list = [
            {
                "exchangeType": 1,
                "tokens": ["99926000"]
            }
        ]

        sws.subscribe(
            correlation_id,
            mode,
            token_list
        )

        print("Subscribed to NIFTY 50")

    def on_error(wsapp, error):
        print("WebSocket error:", error)

    def on_close(wsapp):
        print("WebSocket closed")

    sws.on_data = on_data
    sws.on_open = on_open
    sws.on_error = on_error
    sws.on_close = on_close

    sws.connect()


if __name__ == "__main__":
    main()
```

**Usage**: Run with `RUN_LIVE_ANGEL_TESTS=1 pytest`

**Angel One Integration Library**: The project uses `SmartApi` package for Angel One API access.

---

## 10. Angel One Candle Source (Historical)

**File**: `backend/collectors/market_data/angel_one_candle_source.py`

```python
import os
from datetime import datetime, timedelta

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect

from backend.collectors.market_data.historical_candle_source import (
    HistoricalCandleSource,
)
from backend.collectors.market_data.angel_one_instrument_resolver import (
    AngelOneInstrumentResolver,
)


load_dotenv()


class AngelOneCandleSource(HistoricalCandleSource):
    """Historical candle source backed by Angel One SmartAPI."""

    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.pin = os.getenv("ANGEL_PIN")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        if not all([
            self.api_key,
            self.client_id,
            self.pin,
            self.totp_secret,
        ]):
            raise ValueError(
                "Angel One credentials are missing from .env"
            )

        self.resolver = AngelOneInstrumentResolver()
        self.smart_api = None

    def _login(self):
        totp = pyotp.TOTP(self.totp_secret).now()

        self.smart_api = SmartConnect(
            api_key=self.api_key
        )

        try:
            response = self.smart_api.generateSession(
                self.client_id,
                self.pin,
                totp,
            )
        except Exception:
            raise RuntimeError(
                "Angel One login could not be completed. "
                "The provider may be rate-limiting requests."
            ) from None

        if not response.get("status"):
            raise RuntimeError(
                "Angel One login failed. Check the provider response "
                "and account configuration."
            )

    def fetch(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "ONE_MINUTE",
    ) -> list[dict]:

        self._login()

        instrument = self.resolver.find(
            symbol=symbol,
            exchange="NSE",
        )

        token = instrument["token"]

        start = datetime.strptime(
            listing_date,
            "%Y-%m-%d",
        )

        end = start + timedelta(days=1)

        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": interval,
            "fromdate": start.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "todate": end.strftime(
                "%Y-%m-%d %H:%M"
            ),
        }

        try:
            response = self.smart_api.getCandleData(params)
        except Exception:
            raise RuntimeError(
                "Angel One historical data request could not be "
                "completed. The provider may be rate-limiting requests."
            ) from None

        if not response.get("status"):
            raise RuntimeError(
                "Angel One historical data request was rejected by "
                "the provider."
            )

        candles = response.get("data", [])

        return [
            {
                "timestamp": candle[0],
                "open_price": float(candle[1]),
                "high_price": float(candle[2]),
                "low_price": float(candle[3]),
                "close_price": float(candle[4]),
                "volume": int(candle[5]),
            }
            for candle in candles
        ]
```

**Note**: This is for **historical data** only. For live streaming, the WebSocket test above shows the pattern.

---

## 11. IPO Screening Pipeline

**File**: `backend/services/ipo_screening_service.py`

```python
from backend.storage.ipo_analysis_repository import (
    IPOAnalysisRepository,
)
from backend.storage.ipo_repository import IPORepository
from backend.storage.ipo_rule_repository import (
    IPORuleRepository,
)
from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)
from backend.strategy.ipo_rule_evaluator import (
    IPORuleEvaluator,
)


class IPOScreeningService:
    """Orchestrate IPO analysis and 13-rule screening."""

    def __init__(
        self,
        ipo_repository=None,
        analysis_repository=None,
        rule_repository=None,
        analysis_builder=None,
        rule_evaluator=None,
    ):
        self.ipo_repository = (
            ipo_repository or IPORepository()
        )

        self.analysis_repository = (
            analysis_repository
            or IPOAnalysisRepository()
        )

        self.rule_repository = (
            rule_repository
            or IPORuleRepository()
        )

        self.analysis_builder = (
            analysis_builder
            or IPOAnalysisBuilder()
        )

        self.rule_evaluator = (
            rule_evaluator
            or IPORuleEvaluator()
        )

    def screen_ipo(
        self,
        *,
        internal_ipo_id: int,
        chittorgarh_ipo_id: int,
        chittorgarh_url: str,
        company_name: str,
        ipo_type: str,
    ) -> dict:

        analysis = self.analysis_builder.build(
            ipo_id=internal_ipo_id,
            chittorgarh_ipo_id=chittorgarh_ipo_id,
            chittorgarh_url=chittorgarh_url,
            company_name=company_name,
            ipo_type=ipo_type,
        )

        self.analysis_repository.insert(
            analysis
        )

        results = self.rule_evaluator.evaluate(
            analysis
        )

        self.rule_repository.save_results(
            internal_ipo_id,
            results,
        )

        passed = sum(
            1
            for result in results
            if result.status == "PASS"
        )

        failed = sum(
            1
            for result in results
            if result.status == "FAIL"
        )

        not_evaluable = sum(
            1
            for result in results
            if result.status == "NOT_EVALUABLE"
        )

        strategy_pass = (
            len(results) == 13
            and passed == 13
        )

        return {
            "ipo_id": internal_ipo_id,
            "company_name": company_name,
            "analysis": analysis,
            "rule_results": results,
            "total_rules": len(results),
            "passed": passed,
            "failed": failed,
            "not_evaluable": not_evaluable,
            "strategy_result": (
                "PASS"
                if strategy_pass
                else "FAIL"
            ),
        }
```

**File**: `backend/services/ipo_screening_runner.py`

```python
from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)
from backend.storage.ipo_screening_repository import (
    IPOScreeningRepository,
)
from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)
from backend.strategy.ipo_rule_evaluator import (
    IPORuleEvaluator,
)


class IPOScreeningRunner:
    """
    Screen persisted Chittorgarh IPO discoveries.

    Lifecycle:

        DISCOVERED
            ↓
        ANALYZING
            ↓
        WATCHING / FAILED / NOT_READY

    Every completed screening run is also persisted.
    """

    def __init__(
        self,
        discovery_repository=None,
        analysis_builder=None,
        rule_evaluator=None,
        screening_repository=None,
    ):
        self.discovery_repository = (
            discovery_repository
            or IPODiscoveryRepository()
        )

        self.analysis_builder = (
            analysis_builder
            or IPOAnalysisBuilder()
        )

        self.rule_evaluator = (
            rule_evaluator
            or IPORuleEvaluator()
        )

        self.screening_repository = (
            screening_repository
            or IPOScreeningRepository()
        )

    def screen_all(self) -> list[dict]:
        """Screen all discovered IPOs."""

        discoveries = (
            self.discovery_repository.get_by_status(
                "DISCOVERED"
            )
            + self.discovery_repository.get_by_status(
                "NOT_READY"
            )
        )

        results = []

        for discovery in discoveries:
            results.append(
                self.screen_discovery(discovery)
            )

        return results

    def screen_discovery(
        self,
        discovery: dict,
    ) -> dict:
        # ... [continues with screening logic]
```

**Pipeline Flow**:
1. `IPOScreeningRunner.screen_all()` - Get DISCOVERED & NOT_READY IPOs
2. `IPOAnalysisBuilder.build()` - Gather company metrics
3. `IPORuleEvaluator.evaluate()` - Run 13 rules
4. `IPOScreeningRepository.save_results()` - Persist results
5. Return PASS/FAIL/NOT_READY status

---

## 12. Paper Trading Tests

### Test: Paper Broker Buy/Sell/P&L

**File**: `backend/tests/test_paper_broker.py`

```python
from datetime import datetime
import pytest
from backend.execution.paper_broker import PaperBroker


def test_paper_broker_buy_sell_and_pnl():
    broker = PaperBroker()

    buy = broker.place_order(
        symbol="HORIZONIND",
        side="BUY",
        quantity=100,
        price=60.00,
        timestamp=datetime(2026, 8, 24, 10, 15),
    )

    assert buy["status"] == "FILLED"
    assert buy["side"] == "BUY"
    assert buy["quantity"] == 100
    assert buy["price"] == 60.00

    position = broker.get_position("HORIZONIND")

    assert position is not None
    assert position["symbol"] == "HORIZONIND"
    assert position["quantity"] == 100
    assert position["average_price"] == 60.00

    sell = broker.place_order(
        symbol="HORIZONIND",
        side="SELL",
        quantity=100,
        price=66.00,
        timestamp=datetime(2026, 8, 24, 10, 30),
    )

    assert sell["status"] == "FILLED"
    assert sell["side"] == "SELL"

    assert broker.get_position("HORIZONIND") is None
    assert broker.get_realized_pnl() == 600.00
```

### Test: Strategy Executor Entry/Exit

**File**: `backend/tests/test_strategy_executor.py`

```python
from datetime import datetime
import pytest
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor


def test_execute_entry():
    broker = PaperBroker()
    executor = StrategyExecutor(broker)

    timestamp = datetime(2026, 8, 29, 10, 0)

    result = executor.execute_entry(
        symbol="TESTIPO",
        quantity=10,
        price=100,
        timestamp=timestamp,
    )

    assert result["action"] == "BUY"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 100

    position = broker.get_position("TESTIPO")

    assert position is not None
    assert position["quantity"] == 10
    assert position["average_price"] == 100


def test_execute_exit():
    broker = PaperBroker()
    executor = StrategyExecutor(broker)

    executor.execute_entry(
        symbol="TESTIPO",
        quantity=10,
        price=100,
        timestamp=datetime(2026, 8, 29, 10, 0),
    )

    result = executor.execute_exit(
        symbol="TESTIPO",
        quantity=10,
        price=110,
        timestamp=datetime(2026, 8, 29, 10, 10),
    )

    assert result["action"] == "SELL"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 110

    assert broker.get_position("TESTIPO") is None
    assert broker.get_realized_pnl() == 100
```

### Test: Paper Trading Engine

**File**: `backend/tests/test_paper_trading_engine.py`

```python
from datetime import datetime
import pytest
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.execution.paper_trading_engine import PaperTradingEngine


def test_buy_decision_is_executed():
    broker = PaperBroker(initial_cash=100000)
    executor = StrategyExecutor(broker)
    engine = PaperTradingEngine(executor)

    result = engine.execute(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        },
        timestamp=datetime(2026, 8, 24, 10, 0),
    )

    assert result["action"] == "BUY"
    assert result["executed"] is True
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 100.0

    position = engine.get_position("TESTIPO")

    assert position is not None
    assert position["quantity"] == 10
    assert position["average_price"] == 100.0


def test_sell_decision_is_executed():
    broker = PaperBroker(initial_cash=100000)
    executor = StrategyExecutor(broker)
    engine = PaperTradingEngine(executor)

    engine.execute(
        {
            "action": "BUY",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 100.0,
        }
    )

    result = engine.execute(
        {
            "action": "SELL",
            "symbol": "TESTIPO",
            "quantity": 10,
            "price": 110.0,
        }
    )

    assert result["action"] == "SELL"
    assert result["executed"] is True

    assert engine.get_position("TESTIPO") is None
    assert engine.get_realized_pnl() == 100.0


def test_no_trade_does_not_reach_broker():
    broker = PaperBroker(initial_cash=100000)
    executor = StrategyExecutor(broker)
    engine = PaperTradingEngine(executor)

    result = engine.execute(
        {
            "action": "NO_TRADE",
            "reason": "Strategy conditions were not satisfied.",
        }
    )

    assert result["action"] == "NO_TRADE"
    assert result["executed"] is False
    assert result["order"] is None
    assert engine.get_orders() == []
```

### Test: IPO Trading Orchestrator

**File**: `backend/tests/test_ipo_trading_orchestrator.py`

```python
from datetime import datetime
import pytest
from backend.execution.execution_service import ExecutionService
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_trading_orchestrator import IPOTradingOrchestrator


def make_orchestrator():
    broker = PaperBroker(initial_cash=100000)
    execution_service = ExecutionService(broker)
    strategy_executor = StrategyExecutor(broker)
    orchestrator = IPOTradingOrchestrator(
        execution_service=execution_service,
        strategy_executor=strategy_executor,
    )
    return orchestrator, broker


def test_target_exit():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 105,
                "low": 99,
            },
            {
                "timestamp": datetime(2026, 8, 29, 10, 2),
                "high": 111,
                "low": 104,
            },
        ],
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "TARGET"
    assert result["profit_loss"] == 100
    assert result["profit_loss_percent"] == 10
    assert broker.get_position("TEST") is None


def test_stop_loss_exit():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=10,
        entry_price=100,
        target_price=110,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 101,
                "low": 96,
            },
            {
                "timestamp": datetime(2026, 8, 29, 10, 2),
                "high": 98,
                "low": 94,
            },
        ],
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "STOP_LOSS"
    assert result["profit_loss"] == -50
    assert result["profit_loss_percent"] == -5
    assert broker.get_position("TEST") is None


def test_stop_loss_priority_when_both_levels_hit():
    orchestrator, broker = make_orchestrator()

    result = orchestrator.execute_trade(
        symbol="TEST",
        quantity=5,
        entry_price=100,
        target_price=105,
        stop_loss_price=95,
        candles=[
            {
                "timestamp": datetime(2026, 8, 29, 10, 1),
                "high": 106,
                "low": 94,
            }
        ],
    )

    assert result["status"] == "CLOSED"
    assert result["exit_reason"] == "STOP_LOSS"  # Stop takes priority
    assert result["profit_loss"] == -25
```

### Test: Live Paper Trading Service

**File**: `backend/tests/test_live_paper_trading_service.py`

```python
from datetime import datetime
import pytest
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.live_paper_trading_service import LivePaperTradingService


def make_service():
    broker = PaperBroker(initial_cash=100000)
    executor = StrategyExecutor(broker)
    return LivePaperTradingService(executor)


def test_enter():
    service = make_service()

    result = service.enter(
        symbol="TESTIPO",
        quantity=10,
        price=100,
        timestamp=datetime(2026, 8, 24, 10, 1),
    )

    assert result["action"] == "BUY"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 100

    position = service.get_position("TESTIPO")

    assert position["quantity"] == 10
    assert position["average_price"] == 100


def test_exit():
    service = make_service()

    service.enter(
        symbol="TESTIPO",
        quantity=10,
        price=100,
    )

    result = service.exit(
        symbol="TESTIPO",
        quantity=10,
        price=110,
    )

    assert result["action"] == "SELL"
    assert service.get_position("TESTIPO") is None
    assert service.get_realized_pnl() == 100
```

---

## Architecture Summary

```
Strategy Decision
       ↓
PaperTradingEngine (decision router)
       ↓
StrategyExecutor (validates, delegates)
       ↓
PaperBroker (executes, tracks P&L)
       ↓
Positions, Orders, P&L
```

**Key Points**:
- **StrategyExecutor**: Validation + delegation (broker-agnostic)
- **PaperBroker**: In-memory simulation (no real orders)
- **PaperTradingEngine**: Decision orchestration
- **IPOTradingOrchestrator**: Trade lifecycle (entry + exit conditions)
- **LivePaperTradingService**: Live signal interface

---

## Live Data Flow (WebSocket + Paper Trading)

```
Angel One WebSocket
    ↓ (tick data)
1-minute Candle Accumulation
    ↓ (candle OHLCV)
Strategy Evaluation
    ↓ (BUY/SELL/NO_TRADE)
LivePaperTradingService
    ↓
PaperBroker
    ↓
Position + P&L
```

The WebSocket test shows live connections are possible. For production implementation of live streaming:

1. Authenticate with Angel One SmartConnect
2. Open SmartWebSocketV2 connection
3. Subscribe to instrument tokens
4. Accumulate ticks into 1-minute candles
5. Pass candles to strategy
6. Execute via LivePaperTradingService
