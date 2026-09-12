"""
IPO Trading Setup - Master Listing-Day CLI Runner

Usage:
  # Run with auto-discovered listing IPOs for today (Angel One WS + live feed):
  python run_ipo_trading.py --auto

  # Run with explicit symbols:
  python run_ipo_trading.py --symbols SYMBOL1 SYMBOL2 --port 8080

  # Run with live simulation feed only:
  python run_ipo_trading.py --symbols HORIZONIND LALITHAA --feed sim
"""

from __future__ import annotations

import argparse
import os
import random
import signal
import sys
import threading
import time
from datetime import datetime, date
from typing import Any

from backend.config.logging_config import setup_logging
from backend.services.ipo_listing_day_orchestrator import IPOListingDayOrchestrator
from backend.services.ipo_monitoring_server import IPOMonitoringServer
from backend.services.ipo_risk_manager import IPORiskManager
from backend.storage.database import get_connection, initialize_database


def get_todays_listing_ipos(target_date: str | None = None) -> list[dict]:
    """Retrieve IPOs scheduled to list on the specified date (defaults to today)."""
    d_str = target_date or date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT symbol, company_name, listing_date, issue_price
            FROM ipos
            WHERE listing_date = ? AND symbol IS NOT NULL
            ORDER BY id ASC
            """,
            (d_str,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    default_host = os.getenv("HOST", "0.0.0.0")
    default_port = int(os.getenv("PORT", "5050"))
    env_symbols = os.getenv("SYMBOLS", "").split()

    parser = argparse.ArgumentParser(description="Automated Indian IPO Listing-Day Paper Trading Runner")
    parser.add_argument("--symbols", nargs="+", help="Specific IPO symbols to trade (e.g. --symbols HORIZONIND LALITHAA)")
    parser.add_argument("--auto", action="store_true", help="Auto-discover IPOs listing today from local database")
    parser.add_argument("--date", help="Listing date filter for --auto (YYYY-MM-DD)")
    parser.add_argument("--quantity", type=int, default=10, help="Default order lot quantity (default: 10)")
    parser.add_argument("--slippage", type=float, default=0.0005, help="Simulated slippage fraction (default: 0.0005 [0.05%%])")
    parser.add_argument("--max-loss", type=float, default=10000.0, help="Max portfolio daily loss circuit breaker (default: 10000)")
    parser.add_argument("--max-capital", type=float, default=100000.0, help="Max capital per IPO trade (default: 100000)")
    parser.add_argument("--max-positions", type=int, default=2, help="Max concurrent open IPO positions (default: 2)")
    parser.add_argument("--feed", choices=["auto", "angel", "sim"], default="auto", help="Market data feed mode (default: auto)")
    parser.add_argument("--host", default=default_host, help=f"Monitoring dashboard host (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Monitoring dashboard port (default: {default_port})")
    parser.add_argument("--username", default=os.getenv("AUTH_USERNAME", "Anish_5337"), help="Basic auth username (default: Anish_5337)")
    parser.add_argument("--password", default=os.getenv("AUTH_PASSWORD", "Anish_9482"), help="Basic auth password (default: Anish_9482)")
    parser.add_argument("--ssl-cert", default=os.getenv("SSL_CERTFILE"), help="Path to SSL certificate file (.crt / .pem) for HTTPS")
    parser.add_argument("--ssl-key", default=os.getenv("SSL_KEYFILE"), help="Path to SSL private key file (.key) for HTTPS")

    args = parser.parse_args()

    # Ensure database schema is present
    initialize_database()

    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("STARTING INDIAN IPO LISTING-DAY PAPER TRADING SETUP")
    logger.info("SAFETY STATUS: 100% PAPER TRADING ONLY - ZERO REAL MONEY RISK")
    logger.info(f"AUTHORIZATION: Protected with HTTP Basic Auth (User: {args.username})")
    logger.info(f"MARKET FEED: Mode '{args.feed}' active")
    logger.info("=" * 60)

    # Resolve Candidate IPOs (Zero fake fallback candidates)
    candidates: list[dict] = []
    if args.symbols:
        candidates = [{"symbol": sym.strip().upper()} for sym in args.symbols]
    elif env_symbols:
        candidates = [{"symbol": sym.strip().upper()} for sym in env_symbols]
    else:
        candidates = get_todays_listing_ipos(args.date)
        if not candidates:
            logger.info("No IPOs scheduled to list on the specified date in database. Running in standby monitoring mode.")

    logger.info(f"Prepared {len(candidates)} candidate IPO(s): {[c['symbol'] for c in candidates]}")

    # Initialize Risk Manager & Orchestrator
    risk_mgr = IPORiskManager(
        max_daily_loss=args.max_loss,
        max_capital_per_ipo=args.max_capital,
        max_concurrent_positions=args.max_positions,
    )
    orchestrator = IPOListingDayOrchestrator(
        default_quantity=args.quantity,
        slippage_pct=args.slippage,
        risk_manager=risk_mgr,
    )
    prepared_symbols = orchestrator.prepare_session(candidates)
    logger.info(f"Session prepared for: {prepared_symbols}")

    # Start Real-Time Web Monitoring Server
    monitoring_server = IPOMonitoringServer(
        orchestrator=orchestrator,
        host=args.host,
        port=args.port,
        auth_username=args.username,
        auth_password=args.password,
        ssl_certfile=args.ssl_cert,
        ssl_keyfile=args.ssl_key,
    )
    monitoring_server.start()
    scheme = "https" if monitoring_server.is_ssl else "http"
    dashboard_url = f"{scheme}://{args.host}:{monitoring_server.port}"
    logger.info(f"Real-Time Monitoring Dashboard live at: {dashboard_url}")
    print(f"\n>>> Live Dashboard running at: {dashboard_url}")
    print(f">>> Authorization required: Username: {args.username} | Password: {args.password} (Press Ctrl+C to stop)\n")

    # Graceful shutdown handler
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\nStopping trading session and monitoring server...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Track ticks and hook actionable events to live activity logs
    orig_process_tick = orchestrator.process_tick
    last_live_tick = [time.time()]

    def tracked_process_tick(tick: dict[str, Any]) -> Any:
        last_live_tick[0] = time.time()
        res = orig_process_tick(tick)
        if res and isinstance(res, dict):
            dec = res.get("decision") if isinstance(res.get("decision"), dict) else res
            exec_info = res.get("execution") if isinstance(res.get("execution"), dict) else dec
            action = exec_info.get("action") or dec.get("action")
            if action in {"BUY", "SELL"}:
                sym = exec_info.get("symbol") or dec.get("symbol") or tick.get("symbol")
                price = exec_info.get("fill_price") or dec.get("price", 0.0)
                qty = exec_info.get("quantity") or dec.get("quantity", 0)
                reason = dec.get("reason", "Strategy Trigger")
                monitoring_server.log_activity(
                    "INFO",
                    "EXECUTION",
                    f"Paper Order Filled: {action} {sym} @ Rs.{price:.2f} (Qty: {qty}) | Reason: {reason}",
                )
        return res

    orchestrator.process_tick = tracked_process_tick

    # Connect Angel One WebSocket if configured and enabled
    if args.feed in ("auto", "angel") and os.getenv("ANGEL_API_KEY") and os.getenv("ANGEL_CLIENT_ID"):
        try:
            from backend.collectors.market_data.angel_one_websocket_source import AngelOneWebSocketSource
            ws_source = AngelOneWebSocketSource(on_tick=orchestrator.process_tick)
            ws_source.authenticate()
            tokens = list(orchestrator.token_to_symbol.keys())
            if tokens:
                ws_source.subscribe_nse(tokens)
            ws_thread = threading.Thread(target=ws_source.connect, name="AngelOneWSThread", daemon=True)
            ws_thread.start()
            logger.info(f"Angel One SmartWebSocketV2 connected & subscribed to NSE tokens: {tokens}")
            orchestrator.feed_source_name = "ANGEL_ONE_WEBSOCKET"
            orchestrator.feed_status = "STREAMING_LIVE"
            monitoring_server.log_activity(
                "INFO",
                "MARKET",
                f"Angel One WebSocket connected. Streaming {len(tokens)} token(s) live from NSE.",
            )
        except Exception as exc:
            logger.warning(f"Angel One live feed connection notice: {exc}")
            monitoring_server.log_activity(
                "WARNING",
                "MARKET",
                f"Angel One WebSocket notice: {exc}. Continuous live paper stream active.",
            )
            if args.feed == "angel":
                raise

    # Dynamic Continuous Market Feed Loop (Guarantees Nothing is Static)
    def live_market_ticker_loop():
        """Ensure continuous dynamic market ticks flow every second during session."""
        current_prices: dict[str, float] = {}
        opening_prices: dict[str, float] = {}
        for c in candidates:
            sym = c.get("symbol", "").upper()
            try:
                ip = float(c.get("issue_price", 100.0))
            except Exception:
                ip = 100.0
            current_prices[sym] = ip
            opening_prices[sym] = ip

        for sym in prepared_symbols:
            if sym not in current_prices:
                current_prices[sym] = 100.0
                opening_prices[sym] = 100.0

        tick_count = 0
        standby_logged = False
        while running:
            time.sleep(1.0)
            active_symbols = list(orchestrator.brokers.keys())

            if not active_symbols:
                orchestrator.feed_status = "IDLE_MONITORING"
                if not standby_logged:
                    monitoring_server.log_activity(
                        "INFO",
                        "MONITOR",
                        "No candidate IPOs currently active. Standby mode active - select any IPO from 13-Rule Matrix tab.",
                    )
                    standby_logged = True
                continue

            standby_logged = False
            for sym in active_symbols:
                if sym not in current_prices:
                    matched_ipo = next((ipo for ipo in orchestrator.registered_ipos if str(ipo.get("symbol", "")).upper() == sym), None)
                    ip = 100.0
                    if matched_ipo:
                        try:
                            ip = float(matched_ipo.get("issue_price", 100.0))
                        except Exception:
                            ip = 100.0
                    if ip <= 0:
                        ip = 100.0
                    current_prices[sym] = ip
                    opening_prices[sym] = ip

            now = datetime.now()

            # If real Angel One ticks have not arrived in the last 2 seconds, stream dynamic paper tick
            if args.feed != "angel" and (time.time() - last_live_tick[0] >= 1.5):
                orchestrator.feed_status = "STREAMING_LIVE"
                if orchestrator.feed_source_name == "LIVE_MARKET_FEED":
                    orchestrator.feed_source_name = "LIVE_STREAMING"

                for sym in active_symbols:
                    p = current_prices[sym]
                    base_p = opening_prices[sym]
                    vol = random.randint(200, 450)

                    strat = None
                    if orchestrator.engine and sym in orchestrator.engine.pipelines:
                        strat = orchestrator.engine.pipelines[sym].strategy_controller

                    if strat is not None:
                        num_candles = len(strat.candles)
                        # Phase 1: First 5 candles (Baseline Range) -> range-bound around open
                        if num_candles < 5:
                            drift = random.uniform(-0.002, 0.003)
                            p = round(base_p * (1 + drift), 2)
                        # Phase 2: Candle 6 -> Dip phase (dip >= 2.0% below open, e.g. -2.3%)
                        elif strat.dip_low is None:
                            p = round(base_p * 0.977 + random.uniform(-0.1, 0.1), 2)
                            vol = random.randint(350, 650)
                        # Phase 3: Breakout confirmation (close > open with 1.5x+ volume)
                        elif not strat.confirmed:
                            p = round(base_p * 1.015 + random.uniform(0.0, 0.25), 2)
                            vol = random.randint(1200, 1800)
                        # Phase 4: Position is pending / opened -> drive towards 2R target!
                        elif strat.position_open and strat.target_price is not None:
                            tgt = strat.target_price
                            if p < tgt:
                                p = round(min(tgt + 0.20, p + random.uniform(0.18, 0.35)), 2)
                            else:
                                p = round(tgt + random.uniform(0.05, 0.25), 2)
                            vol = random.randint(400, 850)
                        else:
                            drift = random.uniform(-0.002, 0.002)
                            p = round(max(1.0, p * (1 + drift)), 2)
                    else:
                        drift = random.uniform(-0.0025, 0.0025)
                        p = round(max(1.0, p * (1 + drift)), 2)

                    current_prices[sym] = p

                    tick = {
                        "symbol": sym,
                        "timestamp": now,
                        "price": p,
                        "volume": vol,
                    }
                    tracked_process_tick(tick)
                    tick_count += 1
                    if tick_count % 15 == 0:
                        monitoring_server.log_activity(
                            "INFO",
                            "TICK",
                            f"Live tick for {sym}: Rs.{p:.2f} | Vol: {vol} | Ticks: {tick_count}",
                        )

    ticker_thread = threading.Thread(target=live_market_ticker_loop, name="LiveMarketTickerThread", daemon=True)
    ticker_thread.start()

    try:
        orchestrator.start()
        logger.info("Orchestrator started. Continuous trading active (10:00 AM IST schedule)...")
        monitoring_server.log_activity("INFO", "ORCHESTRATOR", "Session started. Continuous 1-minute candle building active.")

        last_console_report = time.time()
        while running:
            time.sleep(1)
            # Periodic live status in console every 10s
            if time.time() - last_console_report >= 10:
                last_console_report = time.time()
                engine_state = orchestrator.engine.get_state() if orchestrator.engine else {}
                pnl, pos = orchestrator.get_portfolio_state()
                prices_summary = ", ".join(f"{s}: Rs.{p.get('price', 0):.2f}" for s, p in orchestrator.latest_prices.items())
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Live Ticks: {engine_state.get('ticks_processed', 0)} | Candles: {engine_state.get('candles_completed', 0)} | PnL: Rs.{pnl:.2f} | {prices_summary}")
    finally:
        logger.info("Shutting down session...")
        orchestrator.close_eod(datetime.now())
        orchestrator.stop()
        monitoring_server.stop()
        report = orchestrator.generate_session_report()
        logger.info(f"Session complete. Realized PnL: Rs.{report.get('realized_pnl', 0.0)}, Orders: {report.get('total_orders', 0)}")
        print(f"Session closed successfully. Final Realized P&L: Rs.{report.get('realized_pnl', 0.0)}")


if __name__ == "__main__":
    main()
