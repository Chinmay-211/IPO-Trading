"""
IPO Trading Setup - Master Listing-Day CLI Runner

Usage:
  # Run with auto-discovered listing IPOs for today (Angel One WS + live feed):
  python run_ipo_trading.py --auto

  # Run with explicit symbols:
  python run_ipo_trading.py --symbols SYMBOL1 SYMBOL2 --port 8080

  # Run with live simulation feed only:
  python run_ipo_trading.py --symbols <SYMBOL> --feed sim
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

from dotenv import load_dotenv
load_dotenv()

from backend.config.logging_config import setup_logging
from backend.services.ipo_listing_day_orchestrator import IPOListingDayOrchestrator
from backend.services.ipo_monitoring_server import IPOMonitoringServer
from backend.services.ipo_risk_manager import IPORiskManager
from backend.storage.database import get_connection, initialize_database


def get_candidate_ipos(target_date: str | None = None) -> list[dict]:
    """Retrieve IPOs scheduled to list today, or upcoming Mainboard candidates (strictly excluding already-listed IPOs)."""
    d_str = target_date or date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        # 1. Exact listing date match (listing today or requested date)
        rows = conn.execute(
            """
            SELECT symbol, company_name, listing_date, issue_price
            FROM ipos
            WHERE listing_date = ? AND symbol IS NOT NULL AND trim(symbol) != ''
            ORDER BY id ASC
            """,
            (d_str,),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # 2. Upcoming listing dates (strictly > today or upcoming unannounced)
        rows = conn.execute(
            """
            SELECT symbol, company_name, listing_date, issue_price
            FROM ipos
            WHERE (listing_date > ? OR listing_date IS NULL OR listing_date = '')
              AND symbol IS NOT NULL AND trim(symbol) != ''
            ORDER BY 
              CASE WHEN listing_date IS NOT NULL AND trim(listing_date) != '' THEN 0 ELSE 1 END,
              listing_date ASC,
              id ASC
            LIMIT 5
            """,
            (d_str,),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        return []
    finally:
        conn.close()


def ensure_live_ipos_discovered(logger) -> None:
    """Ensure database has real Mainboard IPOs and 13-rule screening runs from Chittorgarh."""
    conn = get_connection()
    try:
        # Strictly purge already-listed IPOs from past dates
        conn.execute("DELETE FROM ipos WHERE listing_date IS NOT NULL AND listing_date != '' AND listing_date < date('now')")
        conn.execute("DELETE FROM ipo_discoveries WHERE listing_date IS NOT NULL AND listing_date != '' AND listing_date < date('now')")
        conn.commit()

        run_count = conn.execute("SELECT count(*) FROM ipo_screening_runs").fetchone()[0]
        ipo_count = conn.execute("SELECT count(*) FROM ipos").fetchone()[0]
    except Exception:
        run_count = 0
        ipo_count = 0
    finally:
        conn.close()

    if run_count > 0 and ipo_count > 0:
        logger.info(f"Database ready: {ipo_count} real Mainboard IPO(s) and {run_count} institutional screening run(s) loaded.")
        return

    logger.info("Initializing real Indian Mainboard IPOs from Chittorgarh...")
    try:
        from backend.services.ipo_discovery_service import IPODiscoveryService
        from backend.services.ipo_screening_runner import IPOScreeningRunner
        d_res = IPODiscoveryService().run()
        logger.info(f"Live Chittorgarh scan: {d_res.get('fetched', 0)} real IPOs fetched, {d_res.get('inserted', 0)} new discoveries.")
        s_res = IPOScreeningRunner().screen_all()
        logger.info(f"13-Rule Institutional Screening evaluated {len(s_res)} real Mainboard IPOs.")
    except Exception as ex:
        logger.warning(f"Startup discovery check: {ex}")


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
    parser.add_argument("--symbols", nargs="+", help="Specific IPO symbols to trade (space-separated)")
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
    parser.add_argument("--ssl", action="store_true", default=os.getenv("SSL_ENABLED", "").lower() in ("true", "1", "yes"), help="Enable HTTPS (auto-generates self-signed certificate for direct IP if none provided)")
    parser.add_argument("--ssl-cert", default=os.getenv("SSL_CERTFILE"), help="Path to SSL certificate file (.crt / .pem) for HTTPS")
    parser.add_argument("--ssl-key", default=os.getenv("SSL_KEYFILE"), help="Path to SSL private key file (.key) for HTTPS")
    parser.add_argument("--rate-limit", type=int, default=int(os.getenv("RATE_LIMIT_RPM", "1200")), help="Rate limit maximum requests per minute per client IP (default: 1200, 0 to disable)")

    args = parser.parse_args()

    # Ensure database schema is present
    initialize_database()

    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("STARTING INDIAN IPO LISTING-DAY PAPER TRADING SETUP")
    logger.info("SAFETY STATUS: 100% PAPER TRADING ONLY - ZERO REAL MONEY RISK")
    logger.info("AUTHORIZATION: Protected with HTTP Basic Auth (Configured via environment / args)")
    logger.info(f"MARKET FEED: Mode '{args.feed}' active")
    logger.info("=" * 60)

    # Automatically discover & screen real Mainboard IPOs if database is fresh
    ensure_live_ipos_discovered(logger)

    # Resolve Candidate IPOs (Real Indian Mainboard candidates)
    candidates: list[dict] = []
    if args.symbols:
        candidates = [{"symbol": sym.strip().upper()} for sym in args.symbols]
    elif env_symbols:
        candidates = [{"symbol": sym.strip().upper()} for sym in env_symbols]
    else:
        candidates = get_candidate_ipos(args.date)
        if not candidates:
            logger.info("No candidate IPOs ready in database. Running in standby monitoring mode.")

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

    # Resolve SSL / TLS configuration for HTTPS
    ssl_cert = args.ssl_cert
    ssl_key = args.ssl_key
    if args.ssl or (ssl_cert and ssl_key):
        if not (ssl_cert and ssl_key and os.path.exists(ssl_cert) and os.path.exists(ssl_key)):
            auto_cert = "data/certs/cert.pem"
            auto_key = "data/certs/key.pem"
            from backend.services.ipo_security import generate_self_signed_cert
            if generate_self_signed_cert(auto_cert, auto_key, ip_or_host=args.host):
                ssl_cert = auto_cert
                ssl_key = auto_key
                logger.info(f"Self-signed SSL certificate ready for IP HTTPS: {ssl_cert}")
            else:
                logger.warning("Could not generate self-signed SSL certificate. Proceeding on HTTP.")

    # Start Real-Time Web Monitoring Server
    monitoring_server = IPOMonitoringServer(
        orchestrator=orchestrator,
        host=args.host,
        port=args.port,
        auth_username=args.username,
        auth_password=args.password,
        ssl_certfile=ssl_cert,
        ssl_keyfile=ssl_key,
        rate_limit_rpm=args.rate_limit,
    )
    monitoring_server.start()
    scheme = "https" if monitoring_server.is_ssl else "http"
    dashboard_url = f"{scheme}://{args.host}:{monitoring_server.port}"
    logger.info(f"Real-Time Monitoring Dashboard live at: {dashboard_url}")
    print(f"\n>>> Live Dashboard running at: {dashboard_url}")
    print(">>> Authorization required: Enter configured AUTH_USERNAME and AUTH_PASSWORD (Press Ctrl+C to stop)\n")

    # Auto-seed live real IPO discoveries if database is fresh/empty
    def _auto_discover_worker():
        try:
            from backend.services.ipo_discovery_service import IPODiscoveryService
            from backend.services.ipo_screening_runner import IPOScreeningRunner
            from backend.services.ipo_monitoring_server import get_recent_screening_matrix
            matrix = get_recent_screening_matrix(limit=1, upcoming_only=False)
            if not matrix:
                logger.info("Local SQLite database has no screening runs. Scanning real Mainboard IPOs from Chittorgarh...")
                d_res = IPODiscoveryService().run()
                logger.info(f"Live Chittorgarh scan complete: {d_res.get('fetched', 0)} IPOs fetched, {d_res.get('inserted', 0)} new discoveries.")
                s_res = IPOScreeningRunner().screen_all()
                logger.info(f"13-Rule Screening evaluated {len(s_res)} real Mainboard IPOs.")
        except Exception as ex:
            logger.warning(f"Background live discovery check skipped: {ex}")

    threading.Thread(target=_auto_discover_worker, name="StartupDiscoveryWorker", daemon=True).start()

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

    ws_source = None
    if args.feed in ("auto", "angel"):
        # Zero silent fallbacks: Fail fast with exact error if Angel One credentials or connection fail
        missing_creds = [
            var for var in ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PIN", "ANGEL_TOTP_SECRET"]
            if not os.getenv(var)
        ]
        if missing_creds:
            raise RuntimeError(
                f"Cannot start live market feed '{args.feed}': Missing credentials in .env: {', '.join(missing_creds)}. "
                f"Please define them in your .env file or run with --feed sim for offline simulation."
            )

        try:
            from backend.collectors.market_data.angel_one_websocket_source import AngelOneWebSocketSource
            ws_source = AngelOneWebSocketSource(on_tick=orchestrator.process_tick)
            ws_source.authenticate()
            tokens = list(orchestrator.token_to_symbol.keys())
            if not tokens:
                logger.warning(f"No NSE tokens resolved for candidates: {prepared_symbols}. Verify symbols exist in Angel One instrument list.")
            else:
                ws_source.subscribe_nse(tokens)
            ws_thread = threading.Thread(target=ws_source.connect, name="AngelOneWSThread", daemon=True)
            ws_thread.start()
            orchestrator.ws_source = ws_source
            logger.info(f"Angel One SmartWebSocketV2 connected & subscribed to NSE tokens: {tokens}")
            orchestrator.feed_source_name = "ANGEL_ONE_WEBSOCKET"
            orchestrator.feed_status = "STREAMING_LIVE"
            monitoring_server.log_activity(
                "INFO",
                "MARKET",
                f"Angel One WebSocket connected. Streaming {len(tokens)} token(s) live from NSE.",
            )
        except Exception as exc:
            logger.error(f"Angel One live feed connection failed: {exc}")
            monitoring_server.log_activity(
                "ALERT",
                "MARKET",
                f"Angel One connection failed: {exc}",
            )
            raise RuntimeError(f"Angel One live feed failed: {exc}") from exc

    # Simulated Market Feed Loop (ONLY active if --feed sim is explicitly requested)
    if args.feed == "sim":
        def _resolve_price_for_symbol(sym: str, candidate_dict: dict | None = None) -> float | None:
            if candidate_dict and candidate_dict.get("issue_price"):
                try:
                    p = float(candidate_dict["issue_price"])
                    if p > 0:
                        return p
                except (ValueError, TypeError):
                    pass

            try:
                conn = get_connection()
                try:
                    row = conn.execute("SELECT issue_price FROM ipos WHERE symbol = ?", (sym,)).fetchone()
                    if row and row[0]:
                        p = float(row[0])
                        if p > 0:
                            return p
                finally:
                    conn.close()
            except Exception:
                pass

            matched = next((ipo for ipo in orchestrator.registered_ipos if str(ipo.get("symbol", "")).upper() == sym), None)
            if matched and matched.get("issue_price"):
                try:
                    p = float(matched["issue_price"])
                    if p > 0:
                        return p
                except (ValueError, TypeError):
                    pass

            return None

        def simulated_market_ticker_loop():
            """Ensure continuous simulated ticks flow every second during offline simulation."""
            current_prices: dict[str, float] = {}
            opening_prices: dict[str, float] = {}
            for c in candidates:
                sym = c.get("symbol", "").upper()
                p = _resolve_price_for_symbol(sym, c)
                if p is not None:
                    current_prices[sym] = p
                    opening_prices[sym] = p

            for sym in prepared_symbols:
                if sym not in current_prices:
                    p = _resolve_price_for_symbol(sym)
                    if p is not None:
                        current_prices[sym] = p
                        opening_prices[sym] = p

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
                        p = _resolve_price_for_symbol(sym)
                        if p is not None:
                            current_prices[sym] = p
                            opening_prices[sym] = p

                now = datetime.now()
                orchestrator.feed_status = "SIMULATED_STREAMING"
                orchestrator.feed_source_name = "SIMULATED_ENGINE"

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
                            f"Simulated tick for {sym}: Rs.{p:.2f} | Vol: {vol} | Ticks: {tick_count}",
                        )

        ticker_thread = threading.Thread(target=simulated_market_ticker_loop, name="SimulatedMarketTickerThread", daemon=True)
        ticker_thread.start()
        logger.info("Simulation mode active (--feed sim). Feeding simulated ticks.")
    else:
        logger.info(f"Market feed mode '{args.feed}': Pure live feed active (Synthetic fallback disabled).")

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
