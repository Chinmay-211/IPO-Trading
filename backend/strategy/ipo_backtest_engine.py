from backend.models.ipo_backtest import IPOBacktestResult


class IPOBacktestEngine:
    """
    Execute a historical IPO trade using supplied market data.

    The engine deliberately does not hard-code the final BUY rule yet.
    Entry/exit logic will be supplied through the strategy configuration.
    """

    def run(
        self,
        ipo_id: int,
        company_name: str,
        strategy_result: str,
        listing_price: float | None,
        opening_price: float | None,
        high_price: float | None,
        low_price: float | None,
        closing_price: float | None,
        stop_loss_percent: float | None = None,
    ) -> IPOBacktestResult:

        if strategy_result != "PASS":
            return IPOBacktestResult(
                ipo_id=ipo_id,
                company_name=company_name,
                strategy_result=strategy_result,
                entry_price=None,
                exit_price=None,
                stop_loss_price=None,
                profit_loss=None,
                profit_loss_percent=None,
                outcome="NO_TRADE",
                reason="IPO did not pass the screening strategy.",
            )

        if opening_price is None:
            return IPOBacktestResult(
                ipo_id=ipo_id,
                company_name=company_name,
                strategy_result=strategy_result,
                entry_price=None,
                exit_price=None,
                stop_loss_price=None,
                profit_loss=None,
                profit_loss_percent=None,
                outcome="NOT_EVALUABLE",
                reason="Opening price is unavailable.",
            )

        if closing_price is None:
            return IPOBacktestResult(
                ipo_id=ipo_id,
                company_name=company_name,
                strategy_result=strategy_result,
                entry_price=None,
                exit_price=None,
                stop_loss_price=None,
                profit_loss=None,
                profit_loss_percent=None,
                outcome="NOT_EVALUABLE",
                reason="Closing price is unavailable.",
            )

        entry_price = opening_price

        stop_loss_price = None

        if stop_loss_percent is not None:
            stop_loss_price = (
                entry_price
                * (1 - stop_loss_percent / 100)
            )

        exit_price = closing_price
        outcome = "CLOSED_AT_CLOSE"
        reason = "Trade closed at listing-day close."

        if (
            stop_loss_price is not None
            and low_price is not None
            and low_price <= stop_loss_price
        ):
            exit_price = stop_loss_price
            outcome = "STOP_LOSS"
            reason = (
                "Listing-day low reached the configured "
                "stop-loss level."
            )

        profit_loss = (
            exit_price - entry_price
        )

        profit_loss_percent = (
            profit_loss
            / entry_price
            * 100
        )

        return IPOBacktestResult(
            ipo_id=ipo_id,
            company_name=company_name,
            strategy_result=strategy_result,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss_price=stop_loss_price,
            profit_loss=profit_loss,
            profit_loss_percent=profit_loss_percent,
            outcome=outcome,
            reason=reason,
        )