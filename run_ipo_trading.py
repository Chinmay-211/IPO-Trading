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
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

from dotenv import load_dotenv
load_dotenv()

from backend.config.logging_config import setup_logging
from backend.services.ipo_listing_day_orchestrator import IPOListingDayOrchestrator
from backend.services.ipo_monitoring_server import IPOMonitoringServer
from backend.services.ipo_risk_manager import IPORiskManager
from backend.storage.database import get_connection, initialize_database


def get_candidate_ipos(target_date: str | None = None) -> list[dict]:
    """Retrieve IPOs scheduled to list today (strictly matching target listing date)."""
    d_str = target_date or date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        # Exact listing date match (listing today or requested date)
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

        return []
    finally:
        conn.close()


def get_next_scheduled_ipo(from_date: str | None = None) -> dict | None:
    """Find the next scheduled Mainboard IPO strictly after from_date."""
    try:
        from backend.services.ipo_monitoring_server import get_recent_screening_matrix
        matrix_items = get_recent_screening_matrix(limit=10, upcoming_only=True)
        for item in matrix_items:
            ld = str(item.get("listing_date") or "").strip()
            if ld and ld.upper() != "TBD":
                return {
                    "symbol": item.get("symbol") or "",
                    "company_name": item.get("company_name"),
                    "listing_date": ld,
                    "issue_price": item.get("issue_price") if item.get("issue_price") != "TBD" else None,
                }
        if matrix_items:
            item = matrix_items[0]
            return {
                "symbol": item.get("symbol") or "",
                "company_name": item.get("company_name"),
                "listing_date": item.get("listing_date", "TBD"),
                "issue_price": item.get("issue_price") if item.get("issue_price") != "TBD" else None,
            }
    except Exception:
        pass
    return None



def ensure_live_ipos_discovered(logger, force: bool = False) -> None:
    """Ensure database has fresh Mainboard IPOs and 13-rule screening runs from Chittorgarh for today."""
    conn = get_connection()
    today_str = date.today().strftime("%Y-%m-%d")
    fresh_today = False
    try:
        # Strictly purge already-listed IPOs from past dates in active candidate table (ipos)
        rows = conn.execute("SELECT id, listing_date FROM ipos WHERE listing_date IS NOT NULL AND listing_date != ''").fetchall()
        for r in rows:
            raw_d = str(r["listing_date"]).strip()
            parsed_d = None
            for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y"):
                try:
                    parsed_d = datetime.strptime(raw_d, fmt).strftime("%Y-%m-%d")
                    break
                except Exception:
                    pass
            if parsed_d:
                if parsed_d < today_str:
                    conn.execute("DELETE FROM ipos WHERE id = ?", (r["id"],))
                elif parsed_d != raw_d:
                    conn.execute("UPDATE ipos SET listing_date = ? WHERE id = ?", (parsed_d, r["id"]))
        conn.commit()

        run_count = conn.execute("SELECT count(*) FROM ipo_screening_runs").fetchone()[0]
        ipo_count = conn.execute("SELECT count(*) FROM ipos").fetchone()[0]
        latest_col = conn.execute("SELECT max(collected_at) FROM ipos").fetchone()[0]
        fresh_today = bool(latest_col and str(latest_col).startswith(today_str))
    except Exception:
        run_count = 0
        ipo_count = 0
    finally:
        conn.close()

    # If data was collected today and we are not forcing a refresh, proceed
    if not force and fresh_today and run_count > 0 and ipo_count > 0:
        logger.info(f"Database ready: {ipo_count} real Mainboard IPO(s) and {run_count} institutional screening run(s) loaded (fresh today: {latest_col}).")
    else:
        logger.info("Pre-market check: Collecting fresh Indian Mainboard IPOs from Chittorgarh before market open...")
        try:
            from backend.services.ipo_discovery_service import IPODiscoveryService
            from backend.services.ipo_screening_runner import IPOScreeningRunner
            d_res = IPODiscoveryService().run()
            logger.info(f"Live Chittorgarh scan: {d_res.get('fetched', 0)} real IPOs fetched, {d_res.get('inserted', 0)} new discoveries.")
            s_res = IPOScreeningRunner().screen_all()
            logger.info(f"13-Rule Institutional Screening evaluated {len(s_res)} real Mainboard IPOs.")
        except Exception as ex:
            logger.warning(f"Pre-market discovery scan: {ex}")

    # Ensure fresh Angel One instruments master is warmed for today
    try:
        from backend.collectors.market_data.angel_one_instrument_resolver import AngelOneInstrumentResolver
        resolver = AngelOneInstrumentResolver()
        if not resolver._is_cache_valid():
            logger.info("Pre-market: Refreshing Angel One instrument master for today's listing scrips...")
            resolver._load_instruments(force_refresh=True)
            logger.info(f"Angel One instrument master warmed ({len(resolver._instruments or [])} scrips).")
    except Exception as exc:
        logger.warning(f"Pre-market Angel One master warming: {exc}")


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
    target_dt = args.date or date.today().strftime("%Y-%m-%d")
    candidates: list[dict] = []
    if args.symbols:
        candidates = [{"symbol": sym.strip().upper()} for sym in args.symbols]
        logger.info(f"Targeting manually specified symbols ({len(candidates)}): {[c['symbol'] for c in candidates]}")
    elif env_symbols:
        candidates = [{"symbol": sym.strip().upper()} for sym in env_symbols]
        logger.info(f"Targeting symbols configured via SYMBOLS env ({len(candidates)}): {[c['symbol'] for c in candidates]}")
    else:
        candidates = get_candidate_ipos(target_dt)
        if not candidates:
            today_weekday = date.today().weekday()
            is_weekend = (today_weekday >= 5) and (not args.date)
            next_ipo = get_next_scheduled_ipo(target_dt)
            next_msg = (
                f"Next scheduled Mainboard listing on NSE: {next_ipo['company_name']} ({next_ipo['symbol']}) on {next_ipo['listing_date']}"
                f"{' (Issue Price: Rs.' + str(next_ipo['issue_price']) + ')' if next_ipo.get('issue_price') else ''}."
                if next_ipo
                else "No upcoming Mainboard listings found in registry."
            )
            if is_weekend:
                logger.info(
                    f"Market is CLOSED today (Weekend: {'Saturday' if today_weekday == 5 else 'Sunday'}, {target_dt}). "
                    f"Zero Mainboard IPOs scheduled to list today."
                )
            else:
                logger.info(
                    f"Zero Mainboard IPOs scheduled to list on NSE/BSE today ({target_dt}). "
                    f"Continuous equity trading is active for existing securities."
                )
            logger.info(f"{next_msg}")
            logger.info("Running in standby monitoring mode. Select any IPO from the 13-Rule Matrix tab or pass --symbols to target early.")

    if candidates:
        logger.info(f"Prepared {len(candidates)} candidate IPO(s): {[c['symbol'] for c in candidates]}")
    else:
        logger.info("Prepared 0 candidate IPO(s) for listing today.")

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
    if prepared_symbols:
        logger.info(f"Session prepared for: {prepared_symbols}")
    else:
        logger.info("Session prepared with 0 active candidate IPOs (Standby mode).")

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

    if not candidates:
        today_weekday = date.today().weekday()
        is_weekend = (today_weekday >= 5) and (not args.date)
        next_ipo = get_next_scheduled_ipo(target_dt)
        next_info = f" Next listing: {next_ipo['company_name']} ({next_ipo['symbol']}) on {next_ipo['listing_date']}." if next_ipo else ""
        monitoring_server.log_activity(
            "INFO",
            "MARKET",
            f"{'Market Closed Today (Weekend).' if is_weekend else '0 IPOs listing today.'}{next_info} Standby mode active.",
        )

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

        def _start_angel_feed():
            nonlocal ws_source
            backoff = 2.0
            from backend.collectors.market_data.angel_one_websocket_source import AngelOneWebSocketSource
            while running:
                try:
                    logger.info("Connecting to Angel One live market feed...")
                    orchestrator.feed_source_name = "ANGEL_ONE_WEBSOCKET"
                    orchestrator.feed_status = "CONNECTING"
                    if ws_source is None:
                        ws_source = AngelOneWebSocketSource(on_tick=orchestrator.process_tick)
                    ws_source.authenticate()
                    tokens = list(orchestrator.token_to_symbol.keys())
                    if tokens:
                        ws_source.subscribe_nse(tokens)
                        logger.info(f"Angel One SmartWebSocketV2 subscribed to tokens: {tokens} for candidates: {prepared_symbols}")
                    else:
                        logger.info("Zero tokens currently registered; WebSocket starting in standby mode.")
                    orchestrator.ws_source = ws_source
                    orchestrator.feed_status = "STREAMING_LIVE"
                    monitoring_server.log_activity(
                        "INFO",
                        "MARKET",
                        f"Angel One WebSocket connected. Streaming {len(tokens)} token(s) live from exchange.",
                    )
                    ws_source.connect()  # blocks while socket is active
                    backoff = 2.0
                except Exception as exc:
                    logger.warning(f"Angel One live feed connection error: {exc}. Retrying in {backoff:.0f}s...")
                    orchestrator.feed_status = f"RECONNECTING ({exc})"
                    monitoring_server.log_activity(
                        "WARNING",
                        "MARKET",
                        f"Angel One feed connection error: {exc}. Retrying in {backoff:.0f}s...",
                    )
                    time.sleep(backoff)
                    backoff = min(30.0, backoff * 1.5)

        ws_thread = threading.Thread(target=_start_angel_feed, name="AngelOneWSThread", daemon=True)
        ws_thread.start()

    # Strict Zero Fake Simulation Policy: Real live Angel One WebSocket feed only
    if args.feed == "sim":
        logger.warning("Fake tick simulation has been removed. Running in pure live market standby mode.")
        orchestrator.feed_status = "STANDBY"
        orchestrator.feed_source_name = "ANGEL_ONE_STANDBY"
    else:
        logger.info(f"Market feed mode '{args.feed}': Pure live Angel One exchange feed active (Zero fake ticks).")

    try:
        orchestrator.start()
        logger.info("Orchestrator started. Continuous trading active (10:00 AM IST schedule)...")
        monitoring_server.log_activity("INFO", "ORCHESTRATOR", "Session started. Continuous 1-minute candle building active.")

        last_console_report = time.time()
        last_tick_count = [0]
        last_tick_time = [time.time()]
        FREEZE_TIMEOUT = 120  # seconds — reconnect if no new ticks in 2 min

        last_token_retry = 0.0
        active_day = [datetime.now(IST).strftime("%Y-%m-%d")]
        last_premarket_refresh = [0.0]

        while running:
            time.sleep(1)

            now_dt = datetime.now(IST)
            today_str = now_dt.strftime("%Y-%m-%d")
            now_ts = time.time()

            # Automatic Pre-Market Fresh Data Collection (08:30 - 09:55 AM IST or date rollover)
            day_changed = (today_str != active_day[0])
            is_premarket = (now_dt.weekday() < 5 and (now_dt.hour == 8 and now_dt.minute >= 30 or now_dt.hour == 9))
            if day_changed or (is_premarket and (now_ts - last_premarket_refresh[0]) >= 600):
                active_day[0] = today_str
                last_premarket_refresh[0] = now_ts
                logger.info(f"[PRE-MARKET] Gathering fresh IPO discoveries and instrument master for {today_str}...")
                try:
                    ensure_live_ipos_discovered(logger, force=day_changed)
                    if not (args.symbols or env_symbols):
                        fresh_cands = get_candidate_ipos(today_str)
                        if fresh_cands:
                            orchestrator.prepare_session(fresh_cands)
                            logger.info(f"[PRE-MARKET] Prepared {len(fresh_cands)} candidate IPO(s): {[c['symbol'] for c in fresh_cands]}")
                            if ws_source is not None:
                                tokens = list(orchestrator.token_to_symbol.keys())
                                if tokens:
                                    ws_source.subscribe_nse(tokens)
                except Exception as _p_exc:
                    logger.warning(f"[PRE-MARKET] Fresh data check warning: {_p_exc}")

            # Auto-resolve tokens for listing day candidates every 10s if any are awaiting tokens
            if (now_ts - last_token_retry) >= 10:
                last_token_retry = now_ts
                if any(
                    str(ipo.get("symbol", "")).strip().upper() not in orchestrator.token_to_symbol.values()
                    for ipo in orchestrator.registered_ipos
                ):
                    newly_resolved = orchestrator.resolve_missing_tokens()
                    if newly_resolved:
                        logger.info(
                            f"Dynamically resolved listing token(s) for: {newly_resolved} "
                            f"(Tokens: {orchestrator.token_to_symbol})"
                        )
                        monitoring_server.log_activity(
                            "INFO",
                            "ORCHESTRATOR",
                            f"Listing token resolved dynamically for: {', '.join(newly_resolved)}",
                        )

            engine_state = orchestrator.engine.get_state() if orchestrator.engine else {}
            current_ticks = engine_state.get("ticks_processed", 0)

            # Update last-tick timestamp whenever the count advances.
            if current_ticks > last_tick_count[0]:
                last_tick_count[0] = current_ticks
                last_tick_time[0] = time.time()

            # Tick-freeze watchdog: detect silent WS disconnect in IST market hours.
            now_dt = datetime.now(IST)
            in_market_hours = (
                now_dt.weekday() < 5
                and 10 <= now_dt.hour < 15
                or (now_dt.hour == 15 and now_dt.minute < 30)
            )
            frozen_secs = time.time() - last_tick_time[0]
            # ponytail: 60s timeout if 0 ticks from startup; FREEZE_TIMEOUT (120s) once active
            timeout = 60 if last_tick_count[0] == 0 else FREEZE_TIMEOUT
            if (
                in_market_hours
                and ws_source is not None
                and frozen_secs > timeout
                and getattr(orchestrator, "token_to_symbol", None)  # only if tokens are registered
            ):
                logger.warning(
                    f"[WATCHDOG] No ticks for {frozen_secs:.0f}s (total ticks: {last_tick_count[0]}) — forcing WS reconnect."
                )
                monitoring_server.log_activity(
                    "WARNING",
                    "MARKET",
                    f"Tick freeze detected ({frozen_secs:.0f}s, {last_tick_count[0]} ticks). Forcing WebSocket reconnect.",
                )
                last_tick_time[0] = time.time()  # reset so we don't spam
                try:
                    ws_source.close()  # triggers _on_close → reconnect thread
                    ws_source._closed = False  # re-arm reconnect
                    # Ensure registered tokens are subscribed upon reconnect
                    tokens = list(orchestrator.token_to_symbol.keys())
                    if tokens:
                        ws_source.subscribe_nse(tokens)
                    import threading as _t
                    _t.Thread(
                        target=ws_source.connect,
                        name="AngelOneWSReconnectWatchdog",
                        daemon=True,
                    ).start()
                except Exception as _exc:
                    logger.error(f"[WATCHDOG] Reconnect failed: {_exc}")

            # Periodic live status in console every 10s
            if time.time() - last_console_report >= 10:
                last_console_report = time.time()
                pnl, pos = orchestrator.get_portfolio_state()
                prices_summary = ", ".join(
                    f"{s}: Rs.{p.get('price', 0):.2f}"
                    for s, p in orchestrator.latest_prices.items()
                )
                print(
                    f"[{now_dt.strftime('%H:%M:%S')}] Live Ticks: {current_ticks} | "
                    f"Candles: {engine_state.get('candles_completed', 0)} | "
                    f"PnL: Rs.{pnl:.2f} | {prices_summary}"
                )

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
