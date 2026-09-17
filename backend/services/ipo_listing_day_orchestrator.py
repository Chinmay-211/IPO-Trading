from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.collectors.market_data.angel_one_instrument_resolver import (
    AngelOneInstrumentResolver,
)
from backend.execution.paper_broker import PaperBroker
from backend.execution.strategy_executor import StrategyExecutor
from backend.services.angel_one_live_engine_feeder import (
    AngelOneLiveEngineFeeder,
)
from backend.services.ipo_live_listing_strategy_controller import (
    IPOLiveListingStrategyController,
)
from backend.services.ipo_live_paper_execution_service import (
    IPOLivePaperExecutionService,
)
from backend.services.ipo_live_paper_pipeline import (
    IPOLivePaperPipeline,
)
from backend.services.live_ipo_paper_engine import (
    LiveIPOPaperEngine,
)
from backend.services.live_paper_trading_service import (
    LivePaperTradingService,
)
from backend.services.market_session_service import (
    MarketSessionService,
)


class IPOListingDayOrchestrator:
    """
    Master listing-day orchestrator for Indian IPO trading.

    Coordinates:
      1. Candidate IPO qualification and token resolution (via local cached master).
      2. Multi-IPO paper pipeline and LiveIPOPaperEngine initialization.
      3. AngelOneLiveEngineFeeder setup for WebSocket tick streaming.
      4. 10:00 AM IST continuous trading session management.
      5. End-of-Day (EOD) force square-off and session reporting.

    STRICT SAFETY: 100% PAPER TRADING ONLY.
    """

    def __init__(
        self,
        instrument_resolver: AngelOneInstrumentResolver | None = None,
        session_service: MarketSessionService | None = None,
        default_quantity: int = 10,
        slippage_pct: float = 0.0,
        risk_manager: Any | None = None,
    ):
        self.resolver = (
            instrument_resolver
            if instrument_resolver is not None
            else AngelOneInstrumentResolver()
        )
        self.session_service = (
            session_service
            if session_service is not None
            else MarketSessionService.for_ipo_listing()
        )
        self.default_quantity = max(1, int(default_quantity))
        self.slippage_pct = float(slippage_pct)
        self.risk_manager = risk_manager

        self.engine: LiveIPOPaperEngine | None = None
        self.feeder: AngelOneLiveEngineFeeder | None = None
        self.ws_source: Any | None = None
        self.brokers: dict[str, PaperBroker] = {}
        self.token_to_symbol: dict[str, str] = {}
        self.registered_ipos: list[dict[str, Any]] = []
        self.is_running = False
        self.session_closed = False
        self.feed_source_name = "LIVE_MARKET_FEED"
        self.feed_status = "READY"
        self.latest_prices: dict[str, dict[str, Any]] = {}

    def prepare_session(
        self,
        candidate_ipos: list[dict[str, Any]],
        rule_evaluator: Any | None = None,
    ) -> list[str]:
        """
        Screen candidates, resolve tokens, and build pipelines.

        Returns list of successfully prepared IPO symbols.
        """
        if not isinstance(candidate_ipos, list):
            raise TypeError("candidate_ipos must be a list of IPO dictionaries.")

        qualified_ipos: list[dict[str, Any]] = []

        for ipo in candidate_ipos:
            if not isinstance(ipo, dict):
                continue

            symbol = ipo.get("symbol")
            if not symbol or not isinstance(symbol, str) or not symbol.strip():
                continue

            # Optional rule evaluation filter
            if rule_evaluator is not None:
                eval_func = getattr(rule_evaluator, "evaluate", None)
                if callable(eval_func):
                    eval_result = eval_func(ipo)
                    if not eval_result or not eval_result.get("passed", False):
                        continue

            qualified_ipos.append(ipo)

        pipelines: dict[str, IPOLivePaperPipeline] = {}
        self.brokers.clear()
        self.token_to_symbol.clear()
        self.registered_ipos = qualified_ipos

        for ipo in qualified_ipos:
            raw_symbol = str(ipo["symbol"]).strip().upper()

            # Resolve token from instrument resolver
            token = ""
            try:
                instrument = self.resolver.find(raw_symbol)
                token = str(instrument.get("token", "")).strip()
            except Exception:
                # If resolution fails, check if token was supplied in candidate dict
                token = str(ipo.get("token", "")).strip()

            if token:
                self.token_to_symbol[token] = raw_symbol
            else:
                # ponytail: log the miss so the operator sees it in the event feed.
                # Ceiling: implement BSE token fallback or manual token override in UI.
                import sys
                print(
                    f"[WARNING] No Angel One instrument token resolved for '{raw_symbol}'. "
                    "Live ticks cannot be matched. Check the local instrument master file "
                    "or add 'token' to the candidate IPO dict.",
                    file=sys.stderr,
                )

            broker = PaperBroker(slippage_pct=self.slippage_pct)
            executor = StrategyExecutor(broker)
            paper_service = LivePaperTradingService(executor)
            execution_service = IPOLivePaperExecutionService(
                paper_service=paper_service,
                risk_manager=self.risk_manager,
                portfolio_state_fn=self.get_portfolio_state,
            )
            strategy = IPOLiveListingStrategyController(
                symbol=raw_symbol,
                quantity=self.default_quantity,
            )
            pipeline = IPOLivePaperPipeline(
                strategy_controller=strategy,
                execution_service=execution_service,
            )

            pipelines[raw_symbol] = pipeline
            self.brokers[raw_symbol] = broker

        self.engine = LiveIPOPaperEngine(
            pipelines=pipelines,
            session_service=self.session_service,
        )
        self.feeder = AngelOneLiveEngineFeeder(
            engine=self.engine,
            token_to_symbol=self.token_to_symbol,
        )

        return list(pipelines.keys())

    def register_ipo(self, ipo: dict[str, Any]) -> str:
        """
        Dynamically register and prepare an IPO for live paper trading.
        Supports manual selection from the 13-Rule Screening Matrix.
        """
        if not isinstance(ipo, dict):
            raise TypeError("ipo must be a dictionary.")

        raw_symbol = str(ipo.get("symbol", "")).strip().upper()
        if not raw_symbol:
            import re
            c_name = str(ipo.get("company_name", "")).strip()
            cleaned = re.sub(r"\b(Ltd|Limited|Pvt|Private|India|Co|Corporation)\b", "", c_name, flags=re.IGNORECASE).strip()
            words = [w for w in cleaned.split() if w]
            raw_symbol = re.sub(r"[^A-Za-z0-9]", "", words[0]).upper() if words else "IPO"

        # Resolve token from instrument resolver
        token = ""
        try:
            instrument = self.resolver.find(raw_symbol)
            token = str(instrument.get("token", "")).strip()
        except Exception:
            token = str(ipo.get("token", "")).strip()

        if token:
            self.token_to_symbol[token] = raw_symbol
            if self.feeder is not None:
                self.feeder.token_to_symbol[token] = raw_symbol
            if self.ws_source is not None:
                try:
                    self.ws_source.subscribe_nse([token])
                except Exception:
                    pass

        # Build pipeline if not already present
        if raw_symbol not in self.brokers:
            broker = PaperBroker(slippage_pct=self.slippage_pct)
            executor = StrategyExecutor(broker)
            paper_service = LivePaperTradingService(executor)
            execution_service = IPOLivePaperExecutionService(
                paper_service=paper_service,
                risk_manager=self.risk_manager,
                portfolio_state_fn=self.get_portfolio_state,
            )
            strategy = IPOLiveListingStrategyController(
                symbol=raw_symbol,
                quantity=self.default_quantity,
            )
            pipeline = IPOLivePaperPipeline(
                strategy_controller=strategy,
                execution_service=execution_service,
            )
            self.brokers[raw_symbol] = broker
            if self.engine is not None:
                self.engine.pipelines[raw_symbol] = pipeline
                self.engine.ipos_decisions[raw_symbol] = 0
                if self.is_running and not self.engine.running:
                    self.engine.start()
            else:
                self.prepare_session([ipo])
                if self.is_running:
                    self.start(self.ws_source)

        # Track in registered_ipos if not already present
        clean_ipo = dict(ipo)
        clean_ipo["symbol"] = raw_symbol
        clean_ipo["token"] = token if token else None
        clean_ipo["token_status"] = "RESOLVED" if token else "UNLISTED"

        # Update existing record or append
        replaced = False
        for i, r in enumerate(self.registered_ipos):
            if str(r.get("symbol", "")).upper() == raw_symbol:
                self.registered_ipos[i] = clean_ipo
                replaced = True
                break
        if not replaced:
            self.registered_ipos.append(clean_ipo)

        return raw_symbol

    def unregister_ipo(self, symbol: str) -> bool:
        """
        Dynamically unregister an IPO from live trading pipelines.
        """
        raw_symbol = str(symbol).strip().upper()
        if not raw_symbol:
            return False

        self.brokers.pop(raw_symbol, None)
        if self.engine is not None:
            self.engine.pipelines.pop(raw_symbol, None)
            self.engine.ipos_decisions.pop(raw_symbol, None)

        self.registered_ipos = [
            r for r in self.registered_ipos if str(r.get("symbol", "")).upper() != raw_symbol
        ]
        tokens_to_del = [tok for tok, sym in self.token_to_symbol.items() if sym == raw_symbol]
        for tok in tokens_to_del:
            self.token_to_symbol.pop(tok, None)
            if self.feeder is not None:
                self.feeder.token_to_symbol.pop(tok, None)

        if self.ws_source is not None and tokens_to_del:
            try:
                unsub = getattr(self.ws_source, "unsubscribe_nse", None)
                if callable(unsub):
                    unsub(tokens_to_del)
            except Exception:
                pass

        return True

    def start(self, ws_source: Any | None = None) -> None:
        """Start engine and attach WebSocket source if provided."""
        if self.engine is None or self.feeder is None:
            raise RuntimeError("Session has not been prepared. Call prepare_session() first.")

        if ws_source is not None:
            self.feeder.ws_source = ws_source

        self.feeder.start()
        self.is_running = True
        self.session_closed = False

    def stop(self) -> None:
        """Stop feeder and engine."""
        if self.feeder is not None:
            self.feeder.stop()
        self.is_running = False

    def process_tick(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        """Feed a single live tick directly (useful for tests and socket delegators)."""
        if self.feeder is None:
            raise RuntimeError("Orchestrator is not prepared.")

        if isinstance(tick, dict):
            token = str(tick.get("token", "")).strip()
            raw_sym = str(tick.get("symbol", "")).strip().upper()
            sym = self.token_to_symbol.get(token) or raw_sym
            if sym:
                tick["symbol"] = sym
            price = float(tick.get("price", 0))
            if sym and price > 0:
                open_p = price
                if sym in self.latest_prices:
                    open_p = self.latest_prices[sym].get("open_price", price)
                chg_pct = ((price - open_p) / open_p * 100) if open_p > 0 else 0.0
                self.latest_prices[sym] = {
                    "price": price,
                    "open_price": open_p,
                    "change_pct": round(chg_pct, 2),
                    "volume": tick.get("volume", 0),
                    "last_time": datetime.now().strftime("%H:%M:%S"),
                }

        return self.feeder.on_tick(tick)

    def close_eod(self, timestamp: datetime | None = None) -> dict[str, Any]:
        """Trigger EOD force exit and close market session."""
        if self.engine is None:
            return {"action": "NO_ENGINE", "timestamp": timestamp}

        result = self.engine.close_session(timestamp)
        self.is_running = False
        self.session_closed = True
        return result

    def generate_session_report(self) -> dict[str, Any]:
        """Generate comprehensive end-of-day paper trading report."""
        if self.engine is None:
            return {
                "status": "NOT_PREPARED",
                "registered_symbols": [],
                "total_orders": 0,
                "realized_pnl": 0.0,
            }

        orders: list[dict[str, Any]] = self.engine.get_orders()
        positions: dict[str, Any] = self.engine.get_positions()
        engine_state: dict[str, Any] = self.engine.get_state()

        total_realized_pnl = 0.0
        ipo_breakdown: dict[str, dict[str, Any]] = {}

        for symbol, broker in self.brokers.items():
            broker_orders = broker.get_orders()
            pnl = broker.get_realized_pnl()
            total_realized_pnl += pnl

            ipo_breakdown[symbol] = {
                "orders_count": len(broker_orders),
                "position": broker.get_position(symbol),
                "realized_pnl": round(pnl, 2),
            }

        winning_trades = sum(1 for o in orders if o.get("action") == "SELL" and o.get("pnl", 0) > 0)
        total_exits = sum(1 for o in orders if o.get("action") == "SELL")
        win_rate = (winning_trades / total_exits * 100) if total_exits > 0 else 0.0

        return {
            "status": "CLOSED" if self.session_closed else ("RUNNING" if self.is_running else "READY"),
            "registered_symbols": list(self.engine.pipelines.keys()),
            "total_ticks_processed": engine_state.get("ticks_processed", 0),
            "total_candles_completed": engine_state.get("candles_completed", 0),
            "total_decisions_processed": engine_state.get("decisions_processed", 0),
            "total_orders": len(orders),
            "realized_pnl": round(total_realized_pnl, 2),
            "win_rate_pct": round(win_rate, 2),
            "slippage_pct": self.slippage_pct,
            "risk_manager_active": self.risk_manager is not None,
            "orders": orders,
            "positions": positions,
            "ipo_breakdown": ipo_breakdown,
        }

    def get_portfolio_state(self) -> tuple[float, dict[str, Any]]:
        """Return total realized PnL and active positions across all IPO paper brokers."""
        total_pnl = sum(broker.get_realized_pnl() for broker in self.brokers.values())
        positions = {
            sym: broker.get_position(sym)
            for sym, broker in self.brokers.items()
        }
        return total_pnl, positions
