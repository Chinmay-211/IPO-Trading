from datetime import datetime
from typing import Any

from backend.execution.paper_trading_engine import (
    PaperTradingEngine,
)
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.ipo_historical_backtest_runner import (
    IPOHistoricalBacktestRunner,
)


class IPOPaperTradingRunner:
    """
    Connects the existing IPO historical strategy result
    to the paper-trading execution layer.

    Flow:

        screening
            ->
        IPOHistoricalBacktestRunner
            ->
        strategy trade result
            ->
        paper execution
            ->
        final paper-trading result

    The existing IPO strategy is NOT duplicated here.
    """

    def __init__(
        self,
        backtest_runner=None,
        trading_engine=None,
    ):
        self.backtest_runner = (
            backtest_runner
            or IPOHistoricalBacktestRunner()
        )

        if trading_engine is None:
            broker = PaperBroker(
                initial_cash=100000
            )
            executor = StrategyExecutor(broker)
            trading_engine = PaperTradingEngine(
                executor
            )

        self.trading_engine = trading_engine

    def run_one(
        self,
        screening: dict[str, Any],
        interval: str = "1m",
    ) -> dict[str, Any]:
        """
        Run one IPO through historical strategy evaluation
        and paper execution.

        Historical strategy outcomes such as:

            TARGET
            STOP_LOSS
            NO_TRADE

        are preserved.

        Only an actual strategy entry is sent to the
        paper broker.
        """

        if not isinstance(screening, dict):
            raise ValueError(
                "screening must be a dictionary."
            )

        backtest = self.backtest_runner.run_one(
            screening=screening,
            interval=interval,
        )

        outcome = backtest.get("outcome")

        # ---------------------------------------------------------
        # Strategy could not be evaluated.
        # ---------------------------------------------------------
        if outcome == "NOT_EVALUABLE":
            return {
                "status": "NOT_EVALUABLE",
                "backtest": backtest,
                "paper_trade": None,
                "reason": backtest.get("reason"),
            }

        # ---------------------------------------------------------
        # Strategy produced no trade.
        # ---------------------------------------------------------
        if outcome == "NO_TRADE":
            return {
                "status": "NO_TRADE",
                "backtest": backtest,
                "paper_trade": None,
                "reason": backtest.get("reason"),
            }

        # ---------------------------------------------------------
        # A historical strategy trade exists.
        #
        # Execute the historical entry in paper trading.
        # ---------------------------------------------------------
        entry_price = backtest.get(
            "entry_price"
        )

        entry_time = backtest.get(
            "entry_time"
        )

        symbol = backtest.get("symbol")

        if not symbol:
            return {
                "status": "NOT_EVALUABLE",
                "backtest": backtest,
                "paper_trade": None,
                "reason": (
                    "Historical trade has no symbol."
                ),
            }

        if entry_price is None:
            return {
                "status": "NOT_EVALUABLE",
                "backtest": backtest,
                "paper_trade": None,
                "reason": (
                    "Historical trade has no entry price."
                ),
            }

        # ---------------------------------------------------------
        # For the initial paper-trading integration we use one
        # share per strategy trade.
        #
        # Position sizing will be added as a separate component.
        # ---------------------------------------------------------
        quantity = 1

        paper_entry = self.trading_engine.execute(
            decision={
                "action": "BUY",
                "symbol": symbol,
                "quantity": quantity,
                "price": entry_price,
            },
            timestamp=(
                entry_time
                if isinstance(
                    entry_time,
                    datetime,
                )
                else None
            ),
        )

        # ---------------------------------------------------------
        # Historical strategy already tells us the exit.
        #
        # Replay that exit through PaperBroker.
        # ---------------------------------------------------------
        exit_price = backtest.get(
            "exit_price"
        )

        exit_time = backtest.get(
            "exit_time"
        )

        paper_exit = None

        if exit_price is not None:
            paper_exit = self.trading_engine.execute(
                decision={
                    "action": "SELL",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": exit_price,
                },
                timestamp=(
                    exit_time
                    if isinstance(
                        exit_time,
                        datetime,
                    )
                    else None
                ),
            )

        return {
            "status": "EXECUTED",
            "backtest": backtest,
            "paper_trade": {
                "entry": paper_entry,
                "exit": paper_exit,
                "realized_pnl": (
                    self.trading_engine
                    .get_realized_pnl()
                ),
            },
            "reason": backtest.get("reason"),
        }

    def run_all(
        self,
        screening_results: list[dict[str, Any]],
        interval: str = "1m",
    ) -> list[dict[str, Any]]:
        """Run multiple IPOs through paper trading."""

        results = []

        for screening in screening_results:
            results.append(
                self.run_one(
                    screening=screening,
                    interval=interval,
                )
            )

        return results

    def get_position(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        return self.trading_engine.get_position(
            symbol
        )

    def get_orders(self) -> list[dict[str, Any]]:
        return self.trading_engine.get_orders()

    def get_realized_pnl(self) -> float:
        return self.trading_engine.get_realized_pnl()

    def reset(self) -> None:
        self.trading_engine.reset()