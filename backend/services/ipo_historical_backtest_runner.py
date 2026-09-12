from __future__ import annotations

from typing import Any

from backend.storage.database import get_connection
from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)
from backend.storage.ipo_candle_repository import (
    IPOCandleRepository,
)
from backend.strategy.ipo_listing_day_strategy import (
    IPOListingDayStrategy,
)


class IPOHistoricalBacktestRunner:
    """
    Run the listing-day strategy against persisted historical IPO data.

    Flow:

        screening
            ->
        Chittorgarh discovery
            ->
        internal IPO record
            ->
        persisted listing-day candles
            ->
        listing-day strategy
            ->
        trade result

    Only IPOs whose 13-rule screening result is PASS
    are eligible for trading.
    """

    def __init__(
        self,
        discovery_repository=None,
        candle_repository=None,
        strategy=None,
    ):
        self.discovery_repository = (
            discovery_repository
            or IPODiscoveryRepository()
        )

        self.candle_repository = (
            candle_repository
            or IPOCandleRepository()
        )

        self.strategy = (
            strategy
            or IPOListingDayStrategy()
        )

    @staticmethod
    def _normalize_date(date_value: str | None) -> str | None:
        """
        Normalize supported dates to YYYY-MM-DD.

        Examples:
            2026-08-24
            24-Aug-2026
        """
        if not date_value:
            return None

        value = str(date_value).strip()

        from datetime import datetime

        for date_format in (
            "%Y-%m-%d",
            "%d-%b-%Y",
        ):
            try:
                return datetime.strptime(
                    value,
                    date_format,
                ).strftime("%Y-%m-%d")
            except ValueError:
                continue

        return value

    def _get_internal_ipo(
        self,
        company_name: str,
        listing_date: str,
    ) -> dict | None:
        """
        Resolve the internal IPO record from the ipos table.

        ipo_discoveries is keyed by Chittorgarh IPO ID, while
        candles are linked to the internal ipos.id.

        Horizon example:

            Chittorgarh ID = 2826
            company = Horizon Industrial Parks Ltd.
            internal ipo.id = 201
        """
        normalized_date = self._normalize_date(
            listing_date
        )

        connection = get_connection()

        try:
            # First try exact company + listing date.
            row = connection.execute(
                """
                SELECT *
                FROM ipos
                WHERE company_name = ?
                  AND listing_date = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    company_name,
                    normalized_date,
                ),
            ).fetchone()

            if row:
                return dict(row)

            # Company names can differ slightly between sources,
            # for example:
            #
            # Chittorgarh:
            #   Horizon Industrial Parks Ltd.
            #
            # NSE:
            #   Horizon Industrial Parks Limited
            #
            # Fall back to a normalized company-name comparison.
            company_without_suffix = (
                company_name
                .replace(" Limited", "")
                .replace(" Ltd.", "")
                .replace(" Ltd", "")
                .strip()
                .lower()
            )

            rows = connection.execute(
                """
                SELECT *
                FROM ipos
                WHERE listing_date = ?
                ORDER BY id DESC
                """,
                (normalized_date,),
            ).fetchall()

            for candidate in rows:
                candidate_name = (
                    candidate["company_name"] or ""
                )

                candidate_normalized = (
                    candidate_name
                    .replace(" Limited", "")
                    .replace(" Ltd.", "")
                    .replace(" Ltd", "")
                    .strip()
                    .lower()
                )

                if candidate_normalized == company_without_suffix:
                    return dict(candidate)

            return None

        finally:
            connection.close()

    def run_all(
        self,
        screening_results: list[dict],
        interval: str = "1m",
    ) -> list[dict]:
        results = []

        for screening in screening_results:
            result = self.run_one(
                screening=screening,
                interval=interval,
            )

            results.append(result)

        return results

    @staticmethod
    def calculate_summary_metrics(
        results: list[dict[str, Any]],
        slippage_pct: float = 0.0,
    ) -> dict[str, Any]:
        """
        Calculate key institutional backtest performance metrics.

        Metrics include:
          - Win Rate %
          - Profit Factor
          - Max Drawdown % (peak-to-trough)
          - Risk:Reward Ratio
          - Average Win % / Loss %
          - Net Realized PnL (with realistic slippage)
        """
        if not results:
            return {
                "total_ipos_screened": 0,
                "trades_executed": 0,
                "no_trades": 0,
                "not_evaluable": 0,
                "target_hits": 0,
                "stop_loss_hits": 0,
                "force_exits": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "risk_reward_ratio": 0.0,
                "avg_trade_pnl_pct": 0.0,
                "avg_win_pnl_pct": 0.0,
                "avg_loss_pnl_pct": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "net_pnl": 0.0,
                "slippage_pct": slippage_pct,
            }

        total_screened = len(results)
        not_evaluable = sum(1 for r in results if r.get("outcome") == "NOT_EVALUABLE")
        no_trades = sum(1 for r in results if r.get("outcome") == "NO_TRADE")

        executed_trades: list[dict[str, Any]] = []
        for r in results:
            entry = r.get("entry_price")
            exit_p = r.get("exit_price")
            if entry is not None and exit_p is not None and entry > 0:
                executed_trades.append(r)

        trades_count = len(executed_trades)
        if trades_count == 0:
            return {
                "total_ipos_screened": total_screened,
                "trades_executed": 0,
                "no_trades": no_trades,
                "not_evaluable": not_evaluable,
                "target_hits": 0,
                "stop_loss_hits": 0,
                "force_exits": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "risk_reward_ratio": 0.0,
                "avg_trade_pnl_pct": 0.0,
                "avg_win_pnl_pct": 0.0,
                "avg_loss_pnl_pct": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "net_pnl": 0.0,
                "slippage_pct": slippage_pct,
            }

        trade_pnls: list[float] = []
        trade_pnl_pcts: list[float] = []
        win_pnl_pcts: list[float] = []
        loss_pnl_pcts: list[float] = []

        target_hits = 0
        stop_loss_hits = 0
        force_exits = 0

        for t in executed_trades:
            entry = float(t["entry_price"])
            exit_p = float(t["exit_price"])
            outcome = t.get("outcome")

            if outcome == "TARGET":
                target_hits += 1
            elif outcome == "STOP_LOSS":
                stop_loss_hits += 1
            else:
                force_exits += 1

            eff_entry = entry * (1.0 + slippage_pct)
            eff_exit = exit_p * (1.0 - slippage_pct)
            pnl = eff_exit - eff_entry
            pnl_pct = (pnl / eff_entry) * 100.0

            trade_pnls.append(pnl)
            trade_pnl_pcts.append(pnl_pct)

            if pnl > 0:
                win_pnl_pcts.append(pnl_pct)
            else:
                loss_pnl_pcts.append(pnl_pct)

        winning_count = len(win_pnl_pcts)
        losing_count = len(loss_pnl_pcts)
        win_rate = (winning_count / trades_count) * 100.0

        gross_profit = sum(p for p in trade_pnls if p > 0)
        gross_loss = abs(sum(p for p in trade_pnls if p < 0))
        net_pnl = sum(trade_pnls)

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = 999.0
        else:
            profit_factor = 0.0

        avg_trade_pnl_pct = sum(trade_pnl_pcts) / trades_count
        avg_win_pnl_pct = (sum(win_pnl_pcts) / winning_count) if winning_count > 0 else 0.0
        avg_loss_pnl_pct = (sum(loss_pnl_pcts) / losing_count) if losing_count > 0 else 0.0

        risk_reward_ratio = (
            abs(avg_win_pnl_pct / avg_loss_pnl_pct)
            if avg_loss_pnl_pct != 0
            else 0.0
        )

        # Max Drawdown calculation over cumulative PnL percentage
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for pct in trade_pnl_pcts:
            cumulative += pct
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown

        return {
            "total_ipos_screened": total_screened,
            "trades_executed": trades_count,
            "no_trades": no_trades,
            "not_evaluable": not_evaluable,
            "target_hits": target_hits,
            "stop_loss_hits": stop_loss_hits,
            "force_exits": force_exits,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "risk_reward_ratio": round(risk_reward_ratio, 2),
            "avg_trade_pnl_pct": round(avg_trade_pnl_pct, 2),
            "avg_win_pnl_pct": round(avg_win_pnl_pct, 2),
            "avg_loss_pnl_pct": round(avg_loss_pnl_pct, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_pnl": round(net_pnl, 2),
            "slippage_pct": slippage_pct,
        }

    def run_backtest_with_summary(
        self,
        screening_results: list[dict[str, Any]],
        interval: str = "1m",
        slippage_pct: float = 0.0,
    ) -> dict[str, Any]:
        """Run backtest across all IPOs and return both individual trade results and aggregate summary metrics."""
        trade_results = self.run_all(screening_results=screening_results, interval=interval)
        summary = self.calculate_summary_metrics(results=trade_results, slippage_pct=slippage_pct)
        return {
            "summary": summary,
            "results": trade_results,
        }

    def run_one(
        self,
        screening: dict,
        interval: str = "1m",
    ) -> dict:

        company_name = screening[
            "company_name"
        ]

        chittorgarh_ipo_id = screening[
            "chittorgarh_ipo_id"
        ]

        strategy_result = screening.get(
            "strategy_result"
        )

        # ---------------------------------------------------------
        # 1. Find Chittorgarh discovery record.
        # ---------------------------------------------------------
        discovery = (
            self.discovery_repository
            .get_by_chittorgarh_id(
                chittorgarh_ipo_id
            )
        )

        if discovery is None:
            return {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "outcome": "NOT_EVALUABLE",
                "reason": (
                    "IPO discovery record was not found."
                ),
            }

        # ---------------------------------------------------------
        # 2. Screening gate.
        #
        # A failed IPO must never reach the strategy.
        # ---------------------------------------------------------
        if strategy_result != "PASS":
            return {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "outcome": "NO_TRADE",
                "reason": (
                    "IPO did not pass the 13-rule "
                    "screening strategy."
                ),
            }

        # ---------------------------------------------------------
        # 3. Listing date.
        # ---------------------------------------------------------
        listing_date = self._normalize_date(
            discovery.get("listing_date")
        )

        if not listing_date:
            return {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "outcome": "NOT_EVALUABLE",
                "reason": (
                    "Listing date is unavailable."
                ),
            }

        # ---------------------------------------------------------
        # 4. Trading symbol.
        # ---------------------------------------------------------
        symbol = screening.get("symbol")

        if not symbol:
            return {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "outcome": "NOT_EVALUABLE",
                "reason": (
                    "Trading symbol is unavailable."
                ),
            }

        # ---------------------------------------------------------
        # 5. Resolve the internal IPO record.
        #
        # IMPORTANT:
        #
        # ipo_discoveries.id / chittorgarh_ipo_id
        # is NOT the same as
        #
        # ipos.id
        #
        # Candles use ipos.id.
        # ---------------------------------------------------------
        internal_ipo = self._get_internal_ipo(
            company_name=company_name,
            listing_date=listing_date,
        )

        if internal_ipo is None:
            return {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "symbol": symbol,
                "listing_date": listing_date,
                "outcome": "NOT_EVALUABLE",
                "reason": (
                    "Internal IPO record was not found."
                ),
            }

        internal_ipo_id = internal_ipo.get("id")

        if internal_ipo_id is None:
            return {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "symbol": symbol,
                "listing_date": listing_date,
                "outcome": "NOT_EVALUABLE",
                "reason": (
                    "Internal IPO record has no ID."
                ),
            }

        # ---------------------------------------------------------
        # 6. Load persisted listing-day candles.
        # ---------------------------------------------------------
        candles = (
            self.candle_repository
            .get_candles_by_ipo(
                ipo_id=internal_ipo_id,
                listing_date=listing_date,
                interval=interval,
            )
        )

        if not candles:
            return {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "ipo_id": internal_ipo_id,
                "symbol": symbol,
                "listing_date": listing_date,
                "outcome": "NOT_EVALUABLE",
                "reason": (
                    "No historical listing-day "
                    "candles are available."
                ),
            }

        # ---------------------------------------------------------
        # 7. Run listing-day strategy.
        # ---------------------------------------------------------
        trade = self.strategy.run(
            candles=candles,
            strategy_result=strategy_result,
        )

        # ---------------------------------------------------------
        # 8. Return complete backtest result.
        # ---------------------------------------------------------
        return {
            "company_name": company_name,
            "chittorgarh_ipo_id": (
                chittorgarh_ipo_id
            ),
            "ipo_id": internal_ipo_id,
            "symbol": symbol,
            "listing_date": listing_date,
            "outcome": trade.outcome,
            "entry_time": trade.entry_time,
            "entry_price": trade.entry_price,
            "stop_loss_price": (
                trade.stop_loss_price
            ),
            "target_price": trade.target_price,
            "exit_time": trade.exit_time,
            "exit_price": trade.exit_price,
            "profit_loss": trade.profit_loss,
            "profit_loss_percent": (
                trade.profit_loss_percent
            ),
            "dip_low": trade.dip_low,
            "dip_percent": trade.dip_percent,
            "confirmation_time": (
                trade.confirmation_time
            ),
            "confirmation_price": (
                trade.confirmation_price
            ),
            "reason": trade.reason,
        }