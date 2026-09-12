from __future__ import annotations

import base64
import hmac
import json
import os
import threading
from datetime import datetime, date, time as dt_time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from backend.services.ipo_security import (
    MAX_PAYLOAD_BYTES,
    SecurityRateLimiter,
    get_client_ip,
    get_security_headers,
    sanitize_symbol,
)

DEFAULT_AUTH_USERNAME = os.getenv("AUTH_USERNAME", "Anish_5337")
DEFAULT_AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Anish_9482")


def get_recent_screening_matrix(limit: int | None = None, upcoming_only: bool = True) -> list[dict[str, Any]]:
    """Fetch real 13-rule screening runs from SQLite, resolving exact listing dates and real-world IPO states."""
    try:
        from datetime import timedelta
        from backend.storage.database import get_connection
        conn = get_connection()
        try:
            runs = conn.execute(
                """
                SELECT r.id, r.chittorgarh_ipo_id, r.company_name, r.screened_at, r.strategy_result, r.passed, r.failed,
                       COALESCE(NULLIF(d.listing_date, ''), NULLIF(i.listing_date, ''), '') as listing_date,
                       d.ipo_open_date,
                       d.ipo_close_date,
                       COALESCE(i.issue_price, 'TBD') as issue_price,
                       COALESCE(i.symbol, '') as symbol
                FROM ipo_screening_runs r
                LEFT JOIN ipo_discoveries d ON r.chittorgarh_ipo_id = d.chittorgarh_ipo_id
                LEFT JOIN ipos i ON (
                    lower(replace(replace(r.company_name, ' Ltd.', ''), ' Limited', '')) =
                    lower(replace(replace(i.company_name, ' Ltd.', ''), ' Limited', ''))
                )
                ORDER BY r.id DESC
                """,
            ).fetchall()

            today = date.today()

            def _parse_d(s: str | None) -> date | None:
                if not s:
                    return None
                for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(s.strip(), fmt).date()
                    except ValueError:
                        pass
                return None

            def _resolve_listing_date(raw_listing: str | None, close_date: str | None) -> tuple[str, date | None]:
                parsed = _parse_d(raw_listing)
                if parsed:
                    return (parsed.strftime("%d-%b-%Y"), parsed)
                c_dt = _parse_d(close_date)
                if c_dt:
                    cur = c_dt
                    added = 0
                    while added < 3:
                        cur += timedelta(days=1)
                        if cur.weekday() < 5:  # Skip Saturday (5) & Sunday (6)
                            added += 1
                    return (cur.strftime("%d-%b-%Y") + " (T+3)", cur)
                return ("TBD", None)

            def _get_ipo_state(open_date_str: str | None, close_date_str: str | None, listing_dt: date | None) -> tuple[str, str]:
                o_dt = _parse_d(open_date_str)
                c_dt = _parse_d(close_date_str)
                if listing_dt and listing_dt == today:
                    return ("Listing Day (T+3 Today)", "badge-green")
                if c_dt and today > c_dt:
                    return ("Allotment & Circular (T+1/T+2)", "badge-cyan")
                if o_dt and c_dt and o_dt <= today <= c_dt:
                    return ("Public Bidding Open", "badge-green")
                if o_dt and today < o_dt:
                    return (f"Upcoming (Opens {o_dt.strftime('%d-%b')})", "badge-amber")
                return ("Upcoming (RHP Filed)", "badge-amber")

            matrix = []
            for run in runs:
                display_date, dt = _resolve_listing_date(run["listing_date"], run["ipo_close_date"])
                # STRICT USER REQUIREMENT: There is no need of already listed IPOs!
                if dt is not None and dt < today:
                    continue

                state_label, badge_class = _get_ipo_state(run["ipo_open_date"], run["ipo_close_date"], dt)
                run_dict = dict(run)
                run_dict["listing_date"] = display_date
                run_dict["ipo_state"] = state_label
                run_dict["ipo_state_badge"] = badge_class

                rules = conn.execute(
                    """
                    SELECT rule_number, rule_name, passed, actual_value, threshold, reason
                    FROM ipo_screening_rule_results
                    WHERE screening_run_id = ?
                    ORDER BY rule_number ASC
                    """,
                    (run["id"],),
                ).fetchall()
                run_dict["rules"] = [dict(r) for r in rules]
                matrix.append(run_dict)
                if limit and len(matrix) >= limit:
                    break
            return matrix
        finally:
            conn.close()
    except Exception:
        return []


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>IPO Listing Day Trading Setup - Live Intelligence Terminal</title>
  <style>
    :root {
      --bg: #070a0f;
      --card: #0f1722;
      --card-sub: #16202e;
      --border: #212f42;
      --border-bright: #2d3f57;
      --text: #e2e8f0;
      --muted: #8896a8;
      --cyan: #38bdf8;
      --cyan-glow: rgba(56, 189, 248, 0.18);
      --green: #10b981;
      --green-glow: rgba(16, 185, 129, 0.2);
      --red: #ef4444;
      --red-glow: rgba(239, 68, 68, 0.2);
      --amber: #f59e0b;
      --amber-glow: rgba(245, 158, 11, 0.2);
      --purple: #a855f7;
      --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font);
      min-height: 100vh;
      padding: 16px 20px 40px;
    }

    /* Header */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 20px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 16px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .radar-dot {
      width: 12px;
      height: 12px;
      background: var(--green);
      border-radius: 50%;
      box-shadow: 0 0 12px var(--green);
      animation: pulse 1.8s infinite;
    }

    @keyframes pulse {
      0% { transform: scale(0.95); opacity: 0.8; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
      70% { transform: scale(1.15); opacity: 1; box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
      100% { transform: scale(0.95); opacity: 0.8; }
    }

    h1 {
      font-size: 19px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 10px;
      letter-spacing: -0.3px;
    }

    .badge {
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-paper { background: var(--green-glow); color: var(--green); border: 1px solid var(--green); }
    .badge-open { background: var(--cyan-glow); color: var(--cyan); border: 1px solid var(--cyan); }
    .badge-amber { background: var(--amber-glow); color: var(--amber); border: 1px solid var(--amber); }

    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .live-pill {
      font-size: 11px;
      font-weight: 700;
      color: var(--green);
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 6px 12px;
      border-radius: 20px;
      display: flex;
      align-items: center;
      gap: 7px;
    }
    .live-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px var(--green);
      animation: pulse-dot 1.4s infinite;
    }
    @keyframes pulse-dot {
      0% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.3; transform: scale(0.75); }
      100% { opacity: 1; transform: scale(1); }
    }

    .clock-pill {
      font-family: monospace;
      font-size: 13px;
      font-weight: 700;
      color: var(--cyan);
      background: #080d14;
      padding: 6px 12px;
      border-radius: 6px;
      border: 1px solid var(--border);
    }

    .btn {
      background: #1a2433;
      color: var(--text);
      border: 1px solid var(--border);
      padding: 7px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn:hover { background: #26354a; color: #fff; }
    .btn-danger { background: var(--red-glow); color: var(--red); border-color: var(--red); }
    .btn-danger:hover { background: var(--red); color: #fff; }
    .btn-primary { background: var(--cyan); color: #070a0f; border: none; }
    .btn-primary:hover { opacity: 0.9; }

    /* Timeline Pipeline Stages */
    .pipeline-bar {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 12px;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      overflow-x: hidden;
      scrollbar-width: none;
      -ms-overflow-style: none;
      gap: 4px;
    }
    .pipeline-bar::-webkit-scrollbar {
      display: none;
      width: 0;
      height: 0;
    }

    .pipe-step {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      color: var(--muted);
      white-space: nowrap;
      transition: all 0.25s ease;
    }
    .pipe-step.active { color: var(--cyan); font-weight: 700; }
    .pipe-step.completed { color: var(--green); font-weight: 600; }
    .pipe-num {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #182230;
      color: var(--muted);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 700;
      border: 1px solid var(--border);
    }
    .pipe-step.active .pipe-num { background: var(--cyan); color: #070a0f; border-color: var(--cyan); }
    .pipe-step.completed .pipe-num { background: var(--green); color: #070a0f; border-color: var(--green); }
    .pipe-sep { color: var(--border-bright); }

    /* Metrics Grid */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }

    .metric-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 16px;
    }
    .metric-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--muted);
      margin-bottom: 4px;
    }
    .metric-value {
      font-size: 22px;
      font-weight: 700;
      color: #fff;
    }
    .metric-value.positive { color: var(--green); }
    .metric-value.negative { color: var(--red); }

    /* Navigation Tabs */
    .nav-tabs {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 16px;
      padding-bottom: 4px;
      overflow-x: auto;
    }

    .tab-btn {
      background: transparent;
      border: none;
      color: var(--muted);
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .tab-btn:hover { color: #fff; background: rgba(255,255,255,0.03); }
    .tab-btn.active { color: var(--cyan); background: var(--cyan-glow); border-bottom: 2px solid var(--cyan); }

    .tab-pane { display: none; }
    .tab-pane.active { display: block; }

    /* Candlestick Chart Area */
    .chart-box {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 16px;
    }

    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      flex-wrap: wrap;
      gap: 12px;
    }

    .chart-legend {
      display: flex;
      gap: 14px;
      font-size: 12px;
      flex-wrap: wrap;
    }
    .legend-item { display: flex; align-items: center; gap: 6px; }
    .legend-line { width: 14px; height: 2px; }

    canvas {
      width: 100%;
      height: 330px;
      display: block;
      background: #090d14;
      border-radius: 8px;
      border: 1px solid #1a2433;
    }

    /* Selected IPO Cards Grid */
    .ipo-cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
      margin-bottom: 16px;
    }

    .ipo-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      position: relative;
    }
    .ipo-card.active-ipo { border-color: var(--cyan); box-shadow: 0 0 15px rgba(56, 189, 248, 0.15); }
    .ipo-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
    .ipo-name { font-size: 14px; font-weight: 700; color: #fff; }
    .ipo-sym { font-size: 12px; color: var(--cyan); font-weight: 600; margin-top: 2px; }

    .ipo-stats-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      padding: 10px 0;
      border-top: 1px solid var(--card-sub);
      border-bottom: 1px solid var(--card-sub);
      margin: 10px 0;
      text-align: center;
    }
    .stat-title { font-size: 10px; color: var(--muted); text-transform: uppercase; }
    .stat-val { font-size: 13px; font-weight: 700; color: #fff; margin-top: 2px; }

    /* Tables */
    .table-container {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow-x: auto;
      margin-bottom: 16px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      text-align: left;
    }

    th {
      background: #141c28;
      color: var(--muted);
      font-weight: 600;
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }

    td {
      padding: 11px 14px;
      border-bottom: 1px solid var(--border);
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(255, 255, 255, 0.02); }

    .pill-pass { background: var(--green-glow); color: var(--green); padding: 2px 6px; border-radius: 4px; font-weight: 700; }
    .pill-fail { background: var(--red-glow); color: var(--red); padding: 2px 6px; border-radius: 4px; font-weight: 700; }
    .tag-buy { color: var(--green); font-weight: 700; }
    .tag-sell { color: var(--red); font-weight: 700; }
    .empty-msg { text-align: center; color: var(--muted); padding: 24px; }

    /* Terminal Activity Stream */
    .terminal-box {
      background: #090e15;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      font-family: Consolas, monospace;
      font-size: 12px;
      height: 380px;
      overflow-y: auto;
      line-height: 1.6;
    }

    .log-line {
      display: flex;
      gap: 12px;
      margin-bottom: 4px;
      border-bottom: 1px solid rgba(255,255,255,0.03);
      padding-bottom: 2px;
    }
    .log-time { color: var(--muted); min-width: 65px; }
    .log-tag { font-weight: 700; min-width: 75px; text-transform: uppercase; font-size: 10px; padding: 1px 5px; border-radius: 3px; height: 18px; display: inline-flex; align-items: center; justify-content: center; }
    .log-tag.INFO { background: rgba(56, 189, 248, 0.15); color: var(--cyan); }
    .log-tag.TRADE { background: rgba(16, 185, 129, 0.15); color: var(--green); }
    .log-tag.ALERT { background: rgba(245, 158, 11, 0.15); color: var(--amber); }
    .log-tag.RULE { background: rgba(168, 85, 247, 0.15); color: var(--purple); }
    .log-msg { color: #cbd5e1; flex-grow: 1; }

    /* Simulator Panel */
    .sim-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px;
      margin-bottom: 16px;
    }
    .form-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }
    .form-group label {
      display: block;
      font-size: 11px;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .form-control {
      width: 100%;
      background: #090d14;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 12px;
      color: #fff;
      font-size: 13px;
    }
    .form-control:focus { outline: none; border-color: var(--cyan); }

    /* Toast */
    #toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #1a2433;
      color: #fff;
      border: 1px solid var(--cyan);
      padding: 12px 18px;
      border-radius: 8px;
      font-size: 13px;
      display: none;
      box-shadow: 0 10px 25px rgba(0,0,0,0.6);
      z-index: 1000;
    }

    /* Responsive Mobile Media Queries */
    @media (max-width: 900px) {
      body { padding: 12px 14px 30px; }
      header { padding: 12px 14px; gap: 12px; }
      .metrics-grid { grid-template-columns: repeat(3, 1fr); gap: 10px; }
      .pipeline-bar { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    }

    @media (max-width: 680px) {
      body { padding: 8px 10px 30px; }

      header {
        flex-direction: column;
        align-items: stretch;
        gap: 12px;
        padding: 12px 14px;
      }

      .brand {
        flex-direction: row;
        align-items: flex-start;
      }

      h1 {
        font-size: 15px;
        flex-wrap: wrap;
        gap: 6px;
      }

      .header-right {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        width: 100%;
      }

      .header-right .live-pill,
      .header-right .clock-pill {
        grid-column: span 1;
        justify-content: center;
        font-size: 11px;
        padding: 6px 8px;
      }

      .header-right .btn,
      .header-right select {
        width: 100%;
        text-align: center;
        padding: 7px 8px;
        font-size: 11px;
      }

      .pipeline-bar {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        justify-content: flex-start;
        padding: 8px 10px;
      }
      .pipe-step { flex-shrink: 0; font-size: 10px; }
      .pipe-num { width: 18px; height: 18px; font-size: 10px; }

      .metrics-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
      }

      .metric-card {
        padding: 10px 12px;
      }

      .metric-label {
        font-size: 10px;
      }

      .metric-value {
        font-size: 17px;
      }

      .nav-tabs {
        -webkit-overflow-scrolling: touch;
        gap: 4px;
        padding-bottom: 6px;
      }

      .tab-btn {
        padding: 7px 12px;
        font-size: 11px;
        flex-shrink: 0;
      }

      .chart-box {
        padding: 12px;
        border-radius: 10px;
      }

      .chart-header {
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
      }

      .chart-header > div:first-child {
        flex-direction: column;
        align-items: stretch !important;
        gap: 8px !important;
      }

      .chart-header select {
        width: 100% !important;
      }

      .chart-legend {
        font-size: 11px;
        gap: 8px;
      }

      canvas {
        height: 260px;
      }

      .ipo-cards-grid {
        grid-template-columns: 1fr;
        gap: 10px;
      }

      .ipo-card {
        padding: 12px;
      }

      .table-container {
        border-radius: 8px;
        -webkit-overflow-scrolling: touch;
      }

      th {
        padding: 8px 10px;
        font-size: 10px;
        white-space: nowrap;
      }

      td {
        padding: 9px 10px;
        font-size: 11px;
        white-space: nowrap;
      }

      .terminal-box {
        height: 280px;
        padding: 10px;
        font-size: 11px;
      }

      .log-line {
        flex-direction: column;
        gap: 2px;
        padding-bottom: 6px;
      }

      .log-time {
        font-size: 10px;
        min-width: auto;
      }

      .sim-card {
        padding: 14px;
      }

      .form-row {
        grid-template-columns: 1fr;
        gap: 10px;
      }

      #toast {
        left: 14px;
        right: 14px;
        bottom: 14px;
        text-align: center;
      }
    }
  </style>
</head>
<body>
  <div id="toast"></div>

  <!-- Authentication Gate Modal -->
  <div id="auth-modal" style="display:none; position:fixed; inset:0; background:rgba(7,10,15,0.95); z-index:9999; backdrop-filter:blur(8px); align-items:center; justify-content:center;">
    <div style="background:#0f1722; border:1px solid var(--cyan); border-radius:12px; padding:32px; width:100%; max-width:400px; box-shadow:0 20px 50px rgba(0,0,0,0.8); text-align:center;">
      <div style="font-size:36px; margin-bottom:8px;">🔒</div>
      <h2 style="color:#fff; font-size:18px; margin-bottom:6px; font-weight:700;">IPO Intelligence Terminal</h2>
      <p style="color:var(--muted); font-size:12px; margin-bottom:20px;">Access restricted. Enter credentials to unlock live listing data.</p>
      
      <div style="text-align:left; margin-bottom:14px;">
        <label style="font-size:11px; color:var(--muted); text-transform:uppercase; font-weight:600; display:block; margin-bottom:4px;">Username</label>
        <input type="text" id="auth-user" class="btn" style="width:100%; text-align:left; background:#16202e; border:1px solid var(--border); padding:10px 12px; color:#fff; border-radius:6px;" placeholder="Enter username..." autocomplete="username">
      </div>
      
      <div style="text-align:left; margin-bottom:16px;">
        <label style="font-size:11px; color:var(--muted); text-transform:uppercase; font-weight:600; display:block; margin-bottom:4px;">Password</label>
        <input type="password" id="auth-pass" class="btn" style="width:100%; text-align:left; background:#16202e; border:1px solid var(--border); padding:10px 12px; color:#fff; border-radius:6px;" placeholder="Enter password..." autocomplete="current-password">
      </div>

      <div id="auth-error" style="color:var(--red); font-size:12px; margin-bottom:14px; display:none;">Invalid username or password.</div>

      <button class="btn btn-primary" style="width:100%; padding:12px; font-size:13px; font-weight:700;" onclick="submitAuthLogin()">Unlock Terminal</button>
    </div>
  </div>

  <header>
    <div class="brand">
      <div class="radar-dot"></div>
      <div>
        <h1>
          IPO Listing Day Live Intelligence Terminal
          <span class="badge badge-paper">100% Paper Trading Only</span>
        </h1>
        <div style="font-size: 11px; color: var(--muted); margin-top: 2px;">
          NSE / BSE Listing Schedule: Continuous Trading Commences at 10:00 AM IST | Entry Cutoff: 14:30 | Force Exit: 15:15
        </div>
      </div>
    </div>
    <div class="header-right">
      <div class="live-pill" id="live-connection-pill"><span class="live-dot" id="live-dot"></span><span id="live-status-text">CONNECTING FEED...</span></div>
      <div class="clock-pill" id="clock">--:--:-- IST</div>
      <button class="btn" onclick="lockTerminal()" title="Lock session">🔒 Lock</button>
      <button class="btn btn-danger" onclick="triggerEODExit()">🛑 Force Exit EOD</button>
      <button class="btn" onclick="fetchData()">🔄 Refresh</button>
      <select id="auto-refresh" class="btn" onchange="updatePolling(this.value)">
        <option value="2000" selected>Auto: 2s</option>
        <option value="5000">Auto: 5s</option>
        <option value="0">Auto: Off</option>
      </select>
    </div>
  </header>

  <!-- Visual Pipeline Timeline (Dynamic) -->
  <div class="pipeline-bar" id="pipeline-bar">
    <div class="pipe-step" id="step-1"><span class="pipe-num">1</span> 09:00 Pre-Open</div>
    <span class="pipe-sep">→</span>
    <div class="pipe-step" id="step-2"><span class="pipe-num">2</span> 09:45 Discovery</div>
    <span class="pipe-sep">→</span>
    <div class="pipe-step" id="step-3"><span class="pipe-num">3</span> 10:00 Open</div>
    <span class="pipe-sep">→</span>
    <div class="pipe-step" id="step-4"><span class="pipe-num">4</span> 10:05 Baseline</div>
    <span class="pipe-sep">→</span>
    <div class="pipe-step" id="step-5"><span class="pipe-num">5</span> Dip & Breakout</div>
    <span class="pipe-sep">→</span>
    <div class="pipe-step" id="step-6"><span class="pipe-num">6</span> 14:30 Cutoff</div>
    <span class="pipe-sep">→</span>
    <div class="pipe-step" id="step-7"><span class="pipe-num">7</span> 15:15 EOD Exit</div>
  </div>

  <!-- Key Metrics Row -->
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-label">Realized P&L</div>
      <div id="m-pnl" class="metric-value">₹0.00</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Strategy Win Rate</div>
      <div id="m-winrate" class="metric-value">0.0%</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Paper Orders Filled</div>
      <div id="m-orders" class="metric-value">0</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Live Ticks Streamed</div>
      <div id="m-ticks" class="metric-value">0</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Completed 1m Candles</div>
      <div id="m-candles" class="metric-value">0</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Simulated Slippage</div>
      <div id="m-slippage" class="metric-value">0.05%</div>
    </div>
  </div>

  <!-- Primary Navigation Tabs -->
  <div class="nav-tabs">
    <button class="tab-btn active" onclick="switchTab('chart')">📈 Live Candlestick Chart & Analysis</button>
    <button class="tab-btn" onclick="switchTab('selected')">🎯 Selected IPOs (<span id="tab-ipo-cnt">0</span>)</button>
    <button class="tab-btn" onclick="switchTab('matrix')">📋 13-Rule Institutional Screening Matrix</button>
    <button class="tab-btn" onclick="switchTab('backend')">🤖 What Backend is Doing (Live Event Feed)</button>
    <button class="tab-btn" onclick="switchTab('simulator')">⚡ Interactive Simulator & Ticks</button>
    <button class="tab-btn" onclick="switchTab('orders')">📝 Orders & Positions</button>
  </div>

  <!-- TAB 1: Live Candlestick Chart -->
  <div id="tab-chart" class="tab-pane active">
    <div class="chart-box">
      <div class="chart-header">
        <div style="display:flex; align-items:center; gap:12px;">
          <label style="font-size:12px; color:var(--muted); font-weight:700;">ACTIVE CANDLESTICK IPO:</label>
          <select id="chart-symbol-select" class="form-control" style="width:180px;" onchange="renderChart()">
            <option value="">(Loading candidates...)</option>
          </select>
          <span id="chart-strategy-badge" class="badge badge-open">STRATEGY: 13-RULE BREAKOUT</span>
        </div>
        <div class="chart-legend">
          <div class="legend-item"><span class="legend-line" style="background:#fff;"></span> Opening Price</div>
          <div class="legend-item"><span class="legend-line" style="background:var(--amber);"></span> -2% Dip Level</div>
          <div class="legend-item"><span class="legend-line" style="background:var(--green);"></span> Breakout Trigger</div>
          <div class="legend-item"><span class="legend-line" style="background:var(--cyan);"></span> 2R Target</div>
          <div class="legend-item"><span class="legend-line" style="background:var(--red);"></span> Stop-Loss (3% Max)</div>
        </div>
      </div>
      <canvas id="candleChart"></canvas>
      <div style="display:flex; justify-content:space-between; margin-top:10px; font-size:12px; color:var(--muted);">
        <div id="chart-info">Waiting for 1-minute candle completion...</div>
        <div>Continuous Trading 1-Minute Interval (NSE / BSE)</div>
      </div>
    </div>
  </div>

  <!-- TAB 2: Selected IPOs -->
  <div id="tab-selected" class="tab-pane">
    <h3 style="font-size:15px; margin-bottom:12px; color:#fff;">Candidate IPOs Selected for Today's Listing Session</h3>
    <div class="ipo-cards-grid" id="selected-ipos-grid">
      <div class="empty-msg">No candidate IPOs prepared.</div>
    </div>
  </div>

  <!-- TAB 3: 13-Rule Screening Matrix -->
  <div id="tab-matrix" class="tab-pane">
    <div class="chart-box">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; flex-wrap:wrap; gap:10px;">
        <div>
          <h3 style="font-size:15px; margin-bottom:4px; color:#fff;">Upcoming IPO Institutional 13-Rule Screening Matrix</h3>
          <p style="font-size:12px; color:var(--muted); margin:0;">
            Quantitative checklist verified from Chittorgarh & RHP data. Select any IPO below or add any symbol manually to trade it.
          </p>
        </div>
        <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
          <span class="badge badge-paper" style="font-size:11px; padding:6px 10px;">📅 Upcoming & Today's IPOs</span>
          <input type="text" id="custom-ipo-sym" class="btn" style="width:140px; text-align:left; background:#16202e; border:1px solid var(--border); padding:6px 10px; font-size:12px; color:#fff; text-transform:uppercase;" placeholder="NSE Symbol">
          <input type="number" id="custom-ipo-price" class="btn" style="width:90px; text-align:left; background:#16202e; border:1px solid var(--border); padding:6px 10px; font-size:12px; color:#fff;" placeholder="Price (₹)">
          <button class="btn btn-primary" onclick="addCustomIPO()" style="font-size:11px; padding:6px 12px; font-weight:700;">➕ Add to Trade</button>
          <button class="btn btn-primary" onclick="triggerDiscovery()" id="btn-discover" style="font-size:11px; padding:6px 12px; font-weight:700; background:linear-gradient(135deg, #0284c7, #0369a1);" title="Fetch real Mainboard IPOs from Chittorgarh and evaluate 13 rules">🌐 Scan Live IPOs</button>
          <button class="btn" onclick="fetchMatrixData()" style="font-size:11px; padding:6px 10px;">🔄 Refresh</button>
        </div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Company Name & Symbol</th>
              <th>Real-World IPO State</th>
              <th>Scheduled Listing Day</th>
              <th>Listing Time (IST)</th>
              <th>Starting (Issue) Price</th>
              <th>Overall Result</th>
              <th>Passed / Failed</th>
              <th>Rule 1 (Exchange)</th>
              <th>Rule 2 (Total Sub)</th>
              <th>Rule 3 (QIB Sub)</th>
              <th>Audit Status</th>
              <th style="text-align:center;">Trading Action</th>
            </tr>
          </thead>
          <tbody id="matrix-body">
            <tr><td colspan="12" class="empty-msg">Loading institutional screening records from SQLite...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- TAB 4: What Backend is Doing (Live Event Stream) -->
  <div id="tab-backend" class="tab-pane">
    <div class="chart-box">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div>
          <h3 style="font-size:15px; color:#fff;">Live Backend Event Stream & Operational Log</h3>
          <div style="font-size:11px; color:var(--muted);">Real-time stream of engine ticks, candle completions, rule evaluations, and order dispatch.</div>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn" onclick="clearLogs()">Clear</button>
          <button class="btn" onclick="fetchBackendActivity()">Refresh Logs</button>
        </div>
      </div>
      <div class="terminal-box" id="terminal-feed">
        <div class="log-line">
          <span class="log-time">10:00:00</span>
          <span class="log-tag INFO">SYSTEM</span>
          <span class="log-msg">Master Listing Day Orchestrator initialized on NSE/BSE schedule.</span>
        </div>
        <div class="log-line">
          <span class="log-time">10:00:00</span>
          <span class="log-tag INFO">SAFETY</span>
          <span class="log-msg">PaperBroker active. 100% Simulated Paper Trading Only. Real-money orders locked.</span>
        </div>
      </div>
    </div>
  </div>

  <!-- TAB 5: Interactive Simulator -->
  <div id="tab-simulator" class="tab-pane">
    <div class="sim-card">
      <h3 style="font-size:15px; margin-bottom:12px; color:#fff;">Inject Test Tick (Zero-Auth Strategy Test)</h3>
      <div class="form-row">
        <div class="form-group">
          <label>Symbol</label>
          <select id="sim-symbol" class="form-control"></select>
        </div>
        <div class="form-group">
          <label>Price (₹)</label>
          <input id="sim-price" type="number" step="0.05" class="form-control" value="100.0">
        </div>
        <div class="form-group">
          <label>Volume</label>
          <input id="sim-volume" type="number" class="form-control" value="100">
        </div>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <button class="btn btn-primary" onclick="injectCustomTick()">⚡ Send Custom Tick</button>
        <button class="btn" onclick="quickSimulateDip()">📉 Simulate 2.5% Dip Below Open</button>
        <button class="btn" onclick="quickSimulateBreakout()">🚀 Simulate Breakout with 1.8x Volume</button>
      </div>
      <div id="sim-result" style="margin-top:14px; padding:12px; background:#070b10; border-radius:6px; font-family:monospace; font-size:12px; color:var(--cyan); display:none;"></div>
    </div>
  </div>

  <!-- TAB 6: Orders & Positions -->
  <div id="tab-orders" class="tab-pane">
    <div class="chart-box">
      <h3 style="font-size:15px; margin-bottom:12px; color:#fff;">Active Paper Positions</h3>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Quantity</th>
              <th>Average Price</th>
              <th>Total Capital</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="positions-body">
            <tr><td colspan="5" class="empty-msg">No active paper positions held.</td></tr>
          </tbody>
        </table>
      </div>

      <h3 style="font-size:15px; margin:20px 0 12px; color:#fff;">Executed Paper Orders Stream</h3>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Action</th>
              <th>Quantity</th>
              <th>Fill Price</th>
              <th>Slippage</th>
              <th>Realized P&L</th>
              <th>Reason / Rule</th>
            </tr>
          </thead>
          <tbody id="orders-body">
            <tr><td colspan="8" class="empty-msg">No orders executed yet in this session.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    let pollInterval = null;
    let globalData = { status: {}, report: {}, ipos: {}, matrix: [] };

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3500);
    }

    function updateClock() {
      const now = new Date();
      document.getElementById('clock').innerText = now.toLocaleTimeString('en-GB') + ' IST';
      updatePipelineTimeline();
    }
    setInterval(updateClock, 1000);
    updateClock();

    function updatePipelineTimeline() {
      const symbols = (globalData.status && globalData.status.registered_symbols) ||
                      (globalData.report && globalData.report.registered_symbols) || [];

      // If no IPO is listing today, keep pipeline in clean standby mode (no fake checkmarks)
      if (symbols.length === 0) {
        for (let i = 1; i <= 7; i++) {
          const el = document.getElementById(`step-${i}`);
          if (!el) continue;
          el.classList.remove('active', 'completed');
          const numEl = el.querySelector('.pipe-num');
          if (numEl) numEl.innerText = i;
        }
        return;
      }

      // Precise IST minute calculation: IST is UTC + 5h 30m = 330 minutes
      const now = new Date();
      const utcMin = now.getUTCHours() * 60 + now.getUTCMinutes();
      const totalMin = (utcMin + 330) % 1440;

      let activeStep = 1;
      if (totalMin < 585) { // before 09:45
        activeStep = 1;
      } else if (totalMin < 600) { // 09:45 - 10:00
        activeStep = 2;
      } else if (totalMin < 601) { // 10:00 AM Listing bell
        activeStep = 3;
      } else if (totalMin < 605) { // 10:01 - 10:05 Baseline range
        activeStep = 4;
      } else if (totalMin < 870) { // 10:05 - 14:30 Continuous trading
        activeStep = 5;
      } else if (totalMin < 915) { // 14:30 - 15:15 Cutoff
        activeStep = 6;
      } else {
        activeStep = 7; // EOD Force exit
      }

      for (let i = 1; i <= 7; i++) {
        const el = document.getElementById(`step-${i}`);
        if (!el) continue;
        el.classList.remove('active', 'completed');
        const numEl = el.querySelector('.pipe-num');
        if (i < activeStep) {
          el.classList.add('completed');
          if (numEl) numEl.innerText = '✓';
        } else if (i === activeStep) {
          el.classList.add('active');
          if (numEl) numEl.innerText = i;
        } else {
          if (numEl) numEl.innerText = i;
        }
      }
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      const targetBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
      if (targetBtn) targetBtn.classList.add('active');

      const pane = document.getElementById(`tab-${tabId}`);
      if (pane) pane.classList.add('active');

      if (tabId === 'chart') renderChart();
      if (tabId === 'backend') fetchBackendActivity();
      if (tabId === 'matrix') fetchMatrixData();
    }

    // Auth & Client Network Gate
    function getAuthHeader() {
      return sessionStorage.getItem('ipo_auth') || localStorage.getItem('ipo_auth');
    }

    function showAuthModal(errMsg) {
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
      const modal = document.getElementById('auth-modal');
      modal.style.display = 'flex';
      const errEl = document.getElementById('auth-error');
      if (errMsg) {
        errEl.innerText = errMsg;
        errEl.style.display = 'block';
      } else {
        errEl.style.display = 'none';
      }
      setTimeout(() => {
        const u = document.getElementById('auth-user');
        if (u && !u.value) {
          u.focus();
        } else {
          const pass = document.getElementById('auth-pass');
          if (pass) pass.focus();
        }
      }, 100);
    }

    function hideAuthModal() {
      document.getElementById('auth-modal').style.display = 'none';
    }

    async function apiFetch(url, options = {}) {
      const headers = Object.assign({}, options.headers || {});
      const auth = getAuthHeader();
      if (auth) {
        headers['Authorization'] = auth;
      }
      const res = await fetch(url, Object.assign({}, options, { headers }));
      if (res.status === 401) {
        showAuthModal('Authentication required. Enter credentials to continue.');
        throw new Error('Unauthorized');
      }
      return res;
    }

    async function submitAuthLogin() {
      const user = document.getElementById('auth-user').value.trim();
      const pass = document.getElementById('auth-pass').value.trim();
      if (!user || !pass) {
        document.getElementById('auth-error').innerText = 'Please enter both username and password.';
        document.getElementById('auth-error').style.display = 'block';
        return;
      }

      const token = 'Basic ' + btoa(user + ':' + pass);
      try {
        const res = await fetch('/api/status', {
          headers: { 'Authorization': token }
        });
        if (res.status === 200) {
          sessionStorage.setItem('ipo_auth', token);
          localStorage.setItem('ipo_auth', token);
          hideAuthModal();
          showToast('Authenticated successfully');
          fetchData();
          fetchMatrixData();
          fetchBackendActivity();
          updatePolling(2000);
        } else {
          document.getElementById('auth-error').innerText = 'Invalid username or password.';
          document.getElementById('auth-error').style.display = 'block';
        }
      } catch (err) {
        document.getElementById('auth-error').innerText = 'Network error during authentication.';
        document.getElementById('auth-error').style.display = 'block';
      }
    }

    function lockTerminal() {
      sessionStorage.removeItem('ipo_auth');
      localStorage.removeItem('ipo_auth');
      const u = document.getElementById('auth-user');
      if (u) u.value = '';
      const p = document.getElementById('auth-pass');
      if (p) p.value = '';
      showAuthModal();
    }

    async function fetchData() {
      try {
        const [statusRes, reportRes, iposRes] = await Promise.all([
          apiFetch('/api/status').then(r => r.json()),
          apiFetch('/api/report').then(r => r.json()),
          apiFetch('/api/ipos').then(r => r.json())
        ]);

        globalData.status = statusRes;
        globalData.report = reportRes;
        globalData.ipos = iposRes;

        renderUI();
      } catch (err) {
        // Handled in apiFetch
      }
    }

    function deriveCleanSymbol(name) {
      if (!name) return 'IPO';
      const clean = name.replace(/\b(Ltd|Limited|India|Technologies|Services|Solutions|Industries|Holdings|Infra|Infrastructure|Enterprises|Corp|Corporation|Co|Company)\b/gi, '')
                        .replace(/[^a-zA-Z0-9]/g, '')
                        .toUpperCase();
      return clean.slice(0, 10) || 'IPO';
    }

    async function fetchMatrixData() {
      try {
        const res = await apiFetch('/api/matrix').then(r => r.json());
        globalData.matrix = Array.isArray(res) ? res : (res.matrix || []);
        renderMatrix();
      } catch (e) {
        console.error('Failed to fetch matrix data', e);
      }
    }

    async function fetchBackendActivity() {
      try {
        const res = await apiFetch('/api/activity').then(r => r.json());
        const logs = res.activity || [];
        const term = document.getElementById('terminal-feed');
        if (logs.length > 0) {
          term.innerHTML = logs.map(l => `
            <div class="log-line">
              <span class="log-time">${l.timestamp}</span>
              <span class="log-tag ${l.level || 'INFO'}">${l.category || 'SYSTEM'}</span>
              <span class="log-msg">${l.message}</span>
            </div>
          `).join('');
        }
      } catch (e) {}
    }

    function renderUI() {
      const { status, report, ipos } = globalData;

      // Update Symbols
      const symbols = report.registered_symbols || status.registered_symbols || [];
      document.getElementById('tab-ipo-cnt').innerText = symbols.length;

      // Update Live Feed Status Badge
      const statusTextEl = document.getElementById('live-status-text');
      const dotEl = document.getElementById('live-dot');
      if (statusTextEl) {
        const src = status.feed_source || 'LIVE STREAM';
        const st = status.feed_status || 'ACTIVE';
        const ticks = status.ticks_processed || 0;
        if (symbols.length === 0) {
          statusTextEl.innerText = `STANDBY: 0 IPOs Listing Today (${src})`;
          if (dotEl) {
            dotEl.style.background = 'var(--cyan)';
            dotEl.style.boxShadow = '0 0 8px var(--cyan)';
          }
        } else {
          statusTextEl.innerText = `${src}: ${st} (${ticks} ticks)`;
          if (dotEl) {
            dotEl.style.background = ticks > 0 ? 'var(--green)' : 'var(--amber)';
            dotEl.style.boxShadow = ticks > 0 ? '0 0 8px var(--green)' : '0 0 8px var(--amber)';
          }
        }
      }

      // Realized PnL & Win rate
      const pnl = report.realized_pnl || 0;
      const pnlEl = document.getElementById('m-pnl');
      pnlEl.innerText = `₹${pnl.toFixed(2)}`;
      pnlEl.className = `metric-value ${pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : ''}`;

      document.getElementById('m-winrate').innerText = `${(report.win_rate_pct || 0).toFixed(1)}%`;
      document.getElementById('m-orders').innerText = (report.orders || []).length;
      document.getElementById('m-ticks').innerText = status.ticks_processed || 0;
      document.getElementById('m-candles').innerText = status.candles_completed || 0;
      document.getElementById('m-slippage').innerText = `${((report.slippage_pct || 0.0005) * 100).toFixed(2)}%`;

      const chartSelect = document.getElementById('chart-symbol-select');
      const simSelect = document.getElementById('sim-symbol');
      const currChart = chartSelect.value;
      const currSim = simSelect.value;

      if (symbols.length === 0) {
        chartSelect.innerHTML = '<option value="">(Standby - 0 IPOs listing today)</option>';
        simSelect.innerHTML = '<option value="">(No IPOs today)</option>';
      } else {
        chartSelect.innerHTML = symbols.map(s => `<option value="${s}">${s}</option>`).join('');
        simSelect.innerHTML = symbols.map(s => `<option value="${s}">${s}</option>`).join('');
        if (currChart && symbols.includes(currChart)) chartSelect.value = currChart;
        if (currSim && symbols.includes(currSim)) simSelect.value = currSim;
      }

      // Render Selected IPO Cards
      renderIPOCards(symbols, ipos);

      // Render Positions Table
      renderPositions(report.positions || {});

      // Render Orders Table
      renderOrders(report.orders || []);

      // If chart tab is open, render chart
      if (document.getElementById('tab-chart').classList.contains('active')) {
        renderChart();
      }

      // If matrix tab is open, ensure matrix rows are in sync
      if (document.getElementById('tab-matrix').classList.contains('active')) {
        renderMatrix();
      }

      // Update timeline state based on active symbols
      updatePipelineTimeline();
    }

    function renderIPOCards(symbols, ipos) {
      const grid = document.getElementById('selected-ipos-grid');
      const registered = ipos.registered_ipos || [];
      const tokens = ipos.token_to_symbol || {};
      const latestPrices = (globalData.status && globalData.status.latest_prices) || {};
      const revTokens = {};
      Object.keys(tokens).forEach(tok => { revTokens[tokens[tok]] = tok; });

      if (symbols.length === 0) {
        grid.innerHTML = '<div class="empty-msg">No candidate IPOs prepared.</div>';
        return;
      }

      grid.innerHTML = symbols.map(sym => {
        const ipoData = registered.find(r => r.symbol === sym) || { symbol: sym };
        const token = revTokens[sym] || ipoData.token || 'RESOLVED';
        const isCurrent = document.getElementById('chart-symbol-select').value === sym;
        const pInfo = latestPrices[sym] || {};
        const ltpText = pInfo.price ? `₹${Number(pInfo.price).toFixed(2)}` : (ipoData.issue_price ? `₹${ipoData.issue_price}` : '₹100.00');
        const chg = pInfo.change_pct !== undefined ? `${pInfo.change_pct >= 0 ? '+' : ''}${pInfo.change_pct.toFixed(2)}%` : '+0.00%';
        const chgColor = (pInfo.change_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)';
        const stage = globalData.status.market_state || 'CONTINUOUS';

        return `
          <div class="ipo-card ${isCurrent ? 'active-ipo' : ''}">
            <div class="ipo-card-header">
              <div>
                <div class="ipo-name">${ipoData.company_name || sym}</div>
                <div class="ipo-sym">NSE / BSE: ${sym}</div>
              </div>
              <span class="badge badge-paper">QUALIFIED</span>
            </div>
            <div class="ipo-stats-row">
              <div><div class="stat-title">Live LTP</div><div class="stat-val" style="color:${chgColor}">${ltpText} <span style="font-size:10px;">(${chg})</span></div></div>
              <div><div class="stat-title">Angel Token</div><div class="stat-val"><code>${token}</code></div></div>
              <div><div class="stat-title">Session State</div><div class="stat-val" style="color:var(--green)">${stage}</div></div>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
              <span style="font-size:11px; color:var(--muted);">13-Rule Check: <strong>PASSED</strong></span>
              <button class="btn" style="padding:4px 8px; font-size:11px;" onclick="selectChartSymbol('${sym}')">View Live Chart</button>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderPositions(positions) {
      const body = document.getElementById('positions-body');
      const active = Object.keys(positions).filter(s => positions[s] && positions[s].quantity > 0);

      if (active.length === 0) {
        body.innerHTML = '<tr><td colspan="5" class="empty-msg">No active paper positions held.</td></tr>';
      } else {
        body.innerHTML = active.map(sym => {
          const pos = positions[sym];
          const total = (pos.quantity * pos.average_price).toFixed(2);
          return `
            <tr>
              <td><strong>${sym}</strong></td>
              <td>${pos.quantity}</td>
              <td>₹${pos.average_price.toFixed(2)}</td>
              <td>₹${total}</td>
              <td><span class="badge badge-paper">ACTIVE LONG</span></td>
            </tr>
          `;
        }).join('');
      }
    }

    function renderOrders(orders) {
      const body = document.getElementById('orders-body');
      if (orders.length === 0) {
        body.innerHTML = '<tr><td colspan="8" class="empty-msg">No orders executed yet in this session.</td></tr>';
      } else {
        body.innerHTML = orders.slice().reverse().map(o => {
          const isBuy = (o.action || o.side) === 'BUY';
          const pnlText = o.pnl !== undefined ? `₹${Number(o.pnl).toFixed(2)}` : '-';
          return `
            <tr>
              <td>${o.timestamp ? new Date(o.timestamp).toLocaleTimeString() : '-'}</td>
              <td><strong>${o.symbol}</strong></td>
              <td class="${isBuy ? 'tag-buy' : 'tag-sell'}">${o.action || o.side}</td>
              <td>${o.quantity}</td>
              <td>₹${Number(o.price || 0).toFixed(2)}</td>
              <td>0.05%</td>
              <td style="color:${o.pnl > 0 ? 'var(--green)' : o.pnl < 0 ? 'var(--red)' : '#fff'}; font-weight:700;">${pnlText}</td>
              <td>${o.reason || 'Strategy rule execution'}</td>
            </tr>
          `;
        }).join('');
      }
    }


    async function toggleSelectIPO(symbol, companyName, issuePrice, action) {
      let sym = symbol;
      if (action === 'select' && (!sym || sym === 'IPO')) {
        const input = prompt('Enter trading symbol for ' + companyName + ':', sym || 'IPO');
        if (!input) return;
        sym = input.trim().toUpperCase();
      }

      let parsedPrice = 100.0;
      if (issuePrice && issuePrice !== 'TBD') {
        const num = parseFloat(issuePrice);
        if (!isNaN(num) && num > 0) parsedPrice = num;
      }

      try {
        const res = await apiFetch('/api/ipos/select', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: action,
            symbol: sym,
            company_name: companyName,
            issue_price: parsedPrice,
          })
        }).then(r => r.json());

        if (res.status === 'OK') {
          await Promise.all([fetchStatus(), fetchReport(), fetchIPOs(), fetchBackendActivity()]);
          renderMatrix();
        } else {
          alert('Error: ' + (res.message || res.error || 'Failed to update selection'));
        }
      } catch (err) {
        console.error('Failed to toggle IPO selection', err);
        alert('Network error while updating IPO selection.');
      }
    }

    async function addCustomIPO() {
      const symInput = document.getElementById('custom-ipo-sym');
      const priceInput = document.getElementById('custom-ipo-price');
      const sym = (symInput.value || '').trim().toUpperCase();
      const price = parseFloat(priceInput.value || '100');
      if (!sym) {
        showToast('Please enter an NSE symbol');
        return;
      }
      await toggleSelectIPO(sym, sym, isNaN(price) || price <= 0 ? 100 : price, 'select');
      symInput.value = '';
      priceInput.value = '';
      showToast(`Added ${sym} to active trading session`);
    }

    async function triggerDiscovery() {
      showToast('Starting live IPO discovery from Chittorgarh...');
      const btn = document.getElementById('btn-discover');
      if (btn) {
        btn.disabled = true;
        btn.innerText = '⏳ Scanning...';
      }
      try {
        const res = await apiFetch('/api/discover', { method: 'POST' }).then(r => r.json());
        showToast(res.message || 'Scanning Chittorgarh & evaluating rules...');
        let checks = 0;
        const poller = setInterval(async () => {
          checks++;
          await fetchMatrixData();
          await fetchBackendActivity();
          if ((globalData.matrix && globalData.matrix.length > 0) || checks >= 20) {
            clearInterval(poller);
            if (btn) {
              btn.disabled = false;
              btn.innerText = '🌐 Scan Live IPOs';
            }
          }
        }, 3000);
      } catch (err) {
        showToast('Discovery request failed: ' + (err.message || err));
        if (btn) {
          btn.disabled = false;
          btn.innerText = '🌐 Scan Live IPOs';
        }
      }
    }

    function renderMatrix() {
      const body = document.getElementById('matrix-body');
      const matrix = globalData.matrix;
      if (!matrix || matrix.length === 0) {
        body.innerHTML = `
          <tr>
            <td colspan="12" style="text-align:center; padding:32px 16px; color:var(--muted); font-size:12px;">
              <div style="font-size:26px; margin-bottom:8px;">📡</div>
              <strong style="color:#fff; font-size:13px;">No upcoming IPO discoveries in local SQLite database.</strong><br>
              <span style="font-size:11px; display:inline-block; margin-top:4px; margin-bottom:12px;">
                Click below to fetch real live Mainboard IPOs from Chittorgarh & evaluate all 13 rules automatically:
              </span><br>
              <button class="btn btn-primary" onclick="triggerDiscovery()" style="font-size:12px; padding:8px 18px; font-weight:700; background:linear-gradient(135deg, #0284c7, #0369a1);">🌐 Scan & Screen Live Mainboard IPOs Now</button>
            </td>
          </tr>
        `;
        return;
      }

      const status = globalData.status || {};
      const report = globalData.report || {};
      const ipos = globalData.ipos || {};
      const activeSymbols = report.registered_symbols || status.registered_symbols || [];
      const registeredList = ipos.registered_ipos || [];

      body.innerHTML = matrix.map(m => {
        const isPass = m.strategy_result === 'PASS';
        const r1 = (m.rules || []).find(r => r.rule_number === 1) || {};
        const r2 = (m.rules || []).find(r => r.rule_number === 2) || {};
        const r3 = (m.rules || []).find(r => r.rule_number === 3) || {};

        const sym = m.symbol || deriveCleanSymbol(m.company_name);
        const isSelected = activeSymbols.includes(sym) || registeredList.some(r => (r.symbol && r.symbol.toUpperCase() === sym.toUpperCase()) || (r.company_name && r.company_name.toLowerCase() === m.company_name.toLowerCase()));

        const symBadge = m.symbol ? `<span class="badge badge-paper" style="margin-left:6px;">${m.symbol}</span>` : `<span class="badge" style="margin-left:6px; opacity:0.65;">${sym}</span>`;
        const priceText = (m.issue_price && m.issue_price !== 'TBD') ? `₹${Number(m.issue_price).toFixed(2)}` : 'TBD';
        const listDate = m.listing_date || 'Upcoming';
        const listTime = listDate !== 'Upcoming' ? '10:00 AM IST' : '10:00 AM IST';
        const stateBadge = m.ipo_state_badge === 'badge-green' ? 'badge-paper' : (m.ipo_state_badge === 'badge-cyan' ? 'badge-open' : 'badge-amber');
        const stateText = m.ipo_state || 'Upcoming';

        const safeCompany = (m.company_name || '').replace(/'/g, "\\'");
        const actionBtn = isSelected
          ? `<button class="btn" onclick="toggleSelectIPO('${sym}', '${safeCompany}', '${m.issue_price}', 'deselect')" style="background:rgba(34,197,94,0.18); border:1px solid var(--green); color:var(--green); font-size:11px; padding:4px 8px; font-weight:700;" title="Click to remove this IPO from active session">✓ Selected <span style="font-size:9px;">(Remove)</span></button>`
          : `<button class="btn" onclick="toggleSelectIPO('${sym}', '${safeCompany}', '${m.issue_price}', 'select')" style="background:var(--accent); color:#fff; font-size:11px; padding:4px 8px; font-weight:700;" title="Manually select this IPO for listing-day trading">➕ Select for Trading</button>`;

        return `
          <tr>
            <td><strong>${m.company_name}</strong>${symBadge}</td>
            <td><span class="badge ${stateBadge}">${stateText}</span></td>
            <td><span style="color:var(--cyan); font-weight:600;">📅 ${listDate}</span></td>
            <td><span style="color:var(--text); font-family:monospace;">⏰ ${listTime}</span></td>
            <td><strong style="color:var(--green); font-size:13px;">${priceText}</strong></td>
            <td><span class="${isPass ? 'pill-pass' : 'pill-fail'}">${m.strategy_result}</span></td>
            <td><span class="pill-pass">${m.passed} Passed / ${m.failed} Failed</span></td>
            <td>${r1.passed ? '✅ ' + (r1.actual_value || 'MAINBOARD') : '❌ ' + (r1.actual_value || 'Failed')}</td>
            <td>${r2.passed ? '✅ ' + (r2.actual_value || 'Passed') : '❌ ' + (r2.actual_value || 'Failed')}</td>
            <td>${r3.passed ? '✅ ' + (r3.actual_value || 'Passed') : '❌ ' + (r3.actual_value || 'Failed')}</td>
            <td><span class="pill-pass">Clean Audit</span></td>
            <td style="text-align:center;">${actionBtn}</td>
          </tr>
        `;
      }).join('');
    }

    function selectChartSymbol(sym) {
      document.getElementById('chart-symbol-select').value = sym;
      switchTab('chart');
    }

    // Dynamic Candlestick Chart Rendering
    async function renderChart() {
      const symbol = document.getElementById('chart-symbol-select').value;
      const canvas = document.getElementById('candleChart');
      if (!canvas) return;

      if (!symbol) {
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, rect.width, rect.height);
        ctx.fillStyle = '#8896a8';
        ctx.font = '14px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('📡 Standby Mode: No IPOs scheduled to list today on NSE / BSE.', rect.width / 2, rect.height / 2 - 12);
        ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillStyle = '#4b5563';
        ctx.fillText('Check "13-Rule Institutional Screening Matrix" tab to view upcoming listing dates & starting prices.', rect.width / 2, rect.height / 2 + 14);
        return;
      }

      let candles = [];
      let currentCandle = null;
      let latestPrice = null;
      try {
        const res = await apiFetch(`/api/candles?symbol=${symbol}`).then(r => r.json());
        candles = res.candles || [];
        currentCandle = res.current_candle || null;
        latestPrice = res.latest_price || null;
      } catch (e) {
        candles = [];
      }

      const ctx = canvas.getContext('2d');
      const dpr = window.devicePixelRatio || 1;

      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);

      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);

      const allCandles = candles.slice();
      if (currentCandle) {
        allCandles.push(Object.assign({}, currentCandle, { _isActive: true }));
      }

      const activePrice = latestPrice || (currentCandle ? currentCandle.close_price : (candles.length > 0 ? candles[candles.length - 1].close_price : null));

      document.getElementById('chart-info').innerText =
        `Symbol: ${symbol} | LTP: ${activePrice ? '₹' + Number(activePrice).toFixed(2) : '--'} | Completed 1m: ${candles.length} | Active Candle: ${currentCandle ? 'Forming...' : 'Ready'} | Baseline: First 5 Candles`;

      if (allCandles.length === 0 && !activePrice) {
        ctx.fillStyle = '#8896a8';
        ctx.font = '13px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Waiting for initial price tick (Continuous trading commences at 10:00 AM IST)...', width / 2, height / 2);
        return;
      }

      let minPrice = Infinity;
      let maxPrice = -Infinity;

      allCandles.forEach(c => {
        if (c.low_price < minPrice) minPrice = c.low_price;
        if (c.high_price > maxPrice) maxPrice = c.high_price;
      });

      if (activePrice) {
        if (activePrice < minPrice) minPrice = activePrice;
        if (activePrice > maxPrice) maxPrice = activePrice;
      }

      if (minPrice === Infinity || maxPrice === -Infinity) {
        minPrice = (activePrice || 100) * 0.98;
        maxPrice = (activePrice || 100) * 1.02;
      }

      const openPrice = allCandles.length > 0 ? allCandles[0].open_price : (activePrice || 100);
      const dipLevel = openPrice * 0.98;
      const targetLevel = openPrice * 1.04;
      const stopLevel = openPrice * 0.97;

      minPrice = Math.min(minPrice, stopLevel) * 0.995;
      maxPrice = Math.max(maxPrice, targetLevel) * 1.005;
      const priceRange = maxPrice - minPrice || 1;

      function getY(p) {
        return height - 30 - ((p - minPrice) / priceRange) * (height - 60);
      }

      function drawHLine(price, color, label, isDash = true) {
        const y = getY(price);
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        if (isDash) ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(40, y);
        ctx.lineTo(width - 80, y);
        ctx.stroke();

        ctx.fillStyle = color;
        ctx.font = '10px monospace';
        ctx.textAlign = 'left';
        ctx.fillText(`${label} ₹${price.toFixed(1)}`, width - 75, y + 3);
        ctx.restore();
      }

      drawHLine(openPrice, '#ffffff', 'OPEN');
      drawHLine(dipLevel, '#f59e0b', '-2% DIP');
      drawHLine(targetLevel, '#38bdf8', '2R TARGET');
      drawHLine(stopLevel, '#ef4444', 'SL (3%)');

      if (activePrice) {
        drawHLine(activePrice, '#10b981', 'LIVE LTP', false);
      }

      if (allCandles.length > 0) {
        const candleWidth = Math.max(6, Math.min(22, (width - 120) / allCandles.length - 4));
        const step = (width - 120) / allCandles.length;

        allCandles.forEach((c, idx) => {
          const x = 50 + idx * step + step / 2;
          const yOpen = getY(c.open_price);
          const yClose = getY(c.close_price);
          const yHigh = getY(c.high_price);
          const yLow = getY(c.low_price);

          const isGreen = c.close_price >= c.open_price;
          const color = isGreen ? '#10b981' : '#ef4444';

          // Wick
          ctx.strokeStyle = color;
          ctx.lineWidth = c._isActive ? 2 : 1.5;
          ctx.beginPath();
          ctx.moveTo(x, yHigh);
          ctx.lineTo(x, yLow);
          ctx.stroke();

          // Body
          ctx.fillStyle = color;
          const bodyTop = Math.min(yOpen, yClose);
          const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));
          ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);

          if (c._isActive) {
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(x - candleWidth / 2 - 1, bodyTop - 1, candleWidth + 2, bodyHeight + 2);
          }
        });
      }
    }

    async function injectCustomTick() {
      const sym = document.getElementById('sim-symbol').value;
      const price = parseFloat(document.getElementById('sim-price').value);
      const volume = parseInt(document.getElementById('sim-volume').value, 10);

      if (!sym || isNaN(price) || isNaN(volume)) {
        showToast('Specify valid Symbol, Price, and Volume.');
        return;
      }

      const res = await apiFetch('/api/tick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: sym, price, volume })
      }).then(r => r.json());

      const resBox = document.getElementById('sim-result');
      resBox.style.display = 'block';
      resBox.innerText = `Tick processed: ₹${price} (Vol: ${volume}). Result: ${JSON.stringify(res.result || 'Ingested to candle')}`;
      showToast(`Tick injected for ${sym} @ ₹${price}`);
      fetchData();
    }

    async function quickSimulateDip() {
      const sym = document.getElementById('sim-symbol').value;
      document.getElementById('sim-price').value = '97.5';
      await injectCustomTick();
    }

    async function quickSimulateBreakout() {
      const sym = document.getElementById('sim-symbol').value;
      document.getElementById('sim-price').value = '101.5';
      document.getElementById('sim-volume').value = '1800';
      await injectCustomTick();
    }

    async function triggerEODExit() {
      if (!confirm('Square-off all active IPO paper positions immediately?')) return;
      await apiFetch('/api/eod_exit', { method: 'POST' }).then(r => r.json());
      showToast('EOD Force Exit complete. Positions squared off.');
      fetchData();
    }

    function clearLogs() {
      document.getElementById('terminal-feed').innerHTML = '';
    }

    function updatePolling(val) {
      if (pollInterval) clearInterval(pollInterval);
      const ms = parseInt(val, 10);
      if (ms > 0 && getAuthHeader()) {
        pollInterval = setInterval(fetchData, ms);
      }
    }

    // Keyboard support for login enter key
    document.addEventListener('DOMContentLoaded', () => {
      const user = document.getElementById('auth-user');
      const pass = document.getElementById('auth-pass');
      if (user) {
        user.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            if (pass && !pass.value) pass.focus();
            else submitAuthLogin();
          }
        });
      }
      if (pass) {
        pass.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') submitAuthLogin();
        });
      }
    });

    // Resize listener for responsive chart on mobile/tablet orientation change
    window.addEventListener('resize', () => {
      if (document.getElementById('tab-chart') && document.getElementById('tab-chart').classList.contains('active')) {
        renderChart();
      }
    });

    // Check credentials on load
    const savedAuth = getAuthHeader();
    if (!savedAuth) {
      showAuthModal();
    } else {
      fetchData();
      fetchMatrixData();
      fetchBackendActivity();
      updatePolling(2000);
    }
  </script>
</body>
</html>
"""


class IPOMonitoringHandler(BaseHTTPRequestHandler):
    """
    Authenticated HTTP request handler enforcing HTTP Basic Authorization,
    production security headers, IP rate limiting, and brute-force protection.
    """

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet server logging."""
        return

    def _client_ip(self) -> str:
        return get_client_ip(self.headers, getattr(self, "client_address", None))

    def _apply_security_headers(self) -> None:
        origin = self.headers.get("Origin")
        allowed_origins = getattr(self.server, "allowed_origins", None)
        is_ssl = getattr(self.server, "is_ssl", False)
        for name, value in get_security_headers(is_ssl=is_ssl, origin=origin, allowed_origins=allowed_origins):
            self.send_header(name, value)

    def _check_security_gates(self) -> bool:
        """Enforce rate limits and temporary IP lockouts before handling any request."""
        ip = self._client_ip()
        rate_limiter: SecurityRateLimiter | None = getattr(self.server, "rate_limiter", None)
        if rate_limiter is not None:
            locked, cooldown = rate_limiter.is_locked_out(ip)
            if locked:
                self._send_rate_limited(cooldown)
                return False
            if not rate_limiter.check_rate_limit(ip):
                self._send_rate_limited(60)
                return False
        return True

    def _is_authenticated(self) -> bool:
        ip = self._client_ip()
        rate_limiter: SecurityRateLimiter | None = getattr(self.server, "rate_limiter", None)
        expected_user = getattr(self.server, "auth_username", DEFAULT_AUTH_USERNAME)
        expected_pass = getattr(self.server, "auth_password", DEFAULT_AUTH_PASSWORD)

        auth_header = self.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            if rate_limiter is not None:
                rate_limiter.record_auth_failure(ip)
            return False

        try:
            encoded_cred = auth_header.split(" ", 1)[1].strip()
            decoded = base64.b64decode(encoded_cred).decode("utf-8")
            if ":" not in decoded:
                if rate_limiter is not None:
                    rate_limiter.record_auth_failure(ip)
                return False
            username, password = decoded.split(":", 1)
            valid = hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_pass)
            if rate_limiter is not None:
                if valid:
                    rate_limiter.record_auth_success(ip)
                else:
                    rate_limiter.record_auth_failure(ip)
            return valid
        except Exception:
            if rate_limiter is not None:
                rate_limiter.record_auth_failure(ip)
            return False

    def _send_unauthorized(self, message: str = "Unauthorized. Valid credentials required.") -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="IPO Trading Terminal"')
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._apply_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_rate_limited(self, retry_after: int) -> None:
        body = json.dumps({
            "error": "Too Many Requests. IP address temporarily throttled.",
            "retry_after_seconds": retry_after,
        }).encode("utf-8")
        self.send_response(429)
        self.send_header("Retry-After", str(retry_after))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._apply_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status_code: int, data: Any) -> None:
        serialized = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(serialized)))
        self._apply_security_headers()
        self.end_headers()
        self.wfile.write(serialized)

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight with strict security headers."""
        if not self._check_security_gates():
            return
        self.send_response(204)
        self._apply_security_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if not self._check_security_gates():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        orchestrator = getattr(self.server, "orchestrator", None)

        if path in {"/", "/index.html"}:
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._apply_security_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        # All API endpoints strictly enforce authorization
        if not self._is_authenticated():
            self._send_unauthorized()
            return

        if path == "/api/status":
            if orchestrator is None:
                self._send_json(200, {"status": "UNCONFIGURED"})
                return

            engine_state = orchestrator.engine.get_state() if orchestrator.engine else {}
            latest_prices = getattr(orchestrator, "latest_prices", {})
            feed_source = getattr(orchestrator, "feed_source_name", "LIVE_FEED")
            feed_status = getattr(orchestrator, "feed_status", "STREAMING")
            market_state = "CONTINUOUS"
            if orchestrator.session_service:
                try:
                    market_state = orchestrator.session_service.get_session_state(datetime.now())
                except Exception:
                    market_state = "CONTINUOUS"

            self._send_json(
                200,
                {
                    "is_running": orchestrator.is_running,
                    "session_closed": orchestrator.session_closed,
                    "status": "CLOSED" if orchestrator.session_closed else ("RUNNING" if orchestrator.is_running else "READY"),
                    "registered_symbols": list(orchestrator.brokers.keys()),
                    "ticks_processed": engine_state.get("ticks_processed", 0),
                    "candles_completed": engine_state.get("candles_completed", 0),
                    "decisions_processed": engine_state.get("decisions_processed", 0),
                    "server_time": datetime.now().isoformat(),
                    "market_state": market_state,
                    "feed_source": feed_source,
                    "feed_status": feed_status,
                    "latest_prices": latest_prices,
                },
            )
            return

        if path == "/api/ipos":
            if orchestrator is None:
                self._send_json(200, {"registered_ipos": [], "token_to_symbol": {}})
                return

            self._send_json(
                200,
                {
                    "registered_ipos": orchestrator.registered_ipos,
                    "token_to_symbol": orchestrator.token_to_symbol,
                },
            )
            return

        if path == "/api/matrix":
            matrix = get_recent_screening_matrix(limit=None, upcoming_only=True)
            self._send_json(200, {"matrix": matrix})
            return

        if path == "/api/activity":
            activity = getattr(self.server, "activity_logs", [])
            self._send_json(200, {"activity": activity})
            return

        if path == "/api/candles":
            query_params = parse_qs(parsed.query)
            target_symbol = query_params.get("symbol", [""])[0].strip().upper()

            candles: list[dict[str, Any]] = []
            current_candle = None
            latest_price = None

            if orchestrator and orchestrator.engine:
                for record in orchestrator.engine.results:
                    if not target_symbol or record.get("symbol") == target_symbol:
                        candle_data = record.get("candle")
                        if candle_data:
                            candles.append(candle_data)

                # Get active forming candle from candle builder
                cb = getattr(orchestrator.engine, "candle_builder", None)
                if cb and hasattr(cb, "_active") and target_symbol in cb._active:
                    ac = cb._active[target_symbol]
                    current_candle = {
                        "symbol": ac.symbol,
                        "open_price": ac.open,
                        "high_price": ac.high,
                        "low_price": ac.low,
                        "close_price": ac.close,
                        "volume": ac.volume,
                        "timestamp": ac.timestamp.isoformat(),
                    }
                    latest_price = ac.close

                if latest_price is None and hasattr(orchestrator, "latest_prices") and target_symbol in orchestrator.latest_prices:
                    latest_price = orchestrator.latest_prices[target_symbol].get("price")

            self._send_json(200, {
                "symbol": target_symbol,
                "candles": candles,
                "current_candle": current_candle,
                "latest_price": latest_price,
            })
            return

        if path == "/api/positions":
            if orchestrator is None:
                self._send_json(200, {"positions": {}})
                return

            positions = {
                sym: broker.get_position(sym)
                for sym, broker in orchestrator.brokers.items()
            }
            self._send_json(200, {"positions": positions})
            return

        if path == "/api/orders":
            if orchestrator is None:
                self._send_json(200, {"orders": []})
                return

            orders = orchestrator.engine.get_orders() if orchestrator.engine else []
            self._send_json(200, {"orders": orders})
            return

        if path == "/api/report":
            if orchestrator is None:
                self._send_json(200, {"status": "UNCONFIGURED"})
                return

            report = orchestrator.generate_session_report()
            self._send_json(200, report)
            return

        self._send_json(404, {"error": f"Path '{path}' not found."})

    def do_POST(self) -> None:
        if not self._check_security_gates():
            return

        if not self._is_authenticated():
            self._send_unauthorized()
            return

        parsed = urlparse(self.path)
        path = parsed.path
        orchestrator = getattr(self.server, "orchestrator", None)

        if orchestrator is None:
            self._send_json(503, {"error": "Orchestrator not initialized."})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_PAYLOAD_BYTES:
            self._send_json(413, {"error": f"Payload Too Large. Max allowed size is {MAX_PAYLOAD_BYTES // 1024}KB."})
            return

        body_data = {}
        if content_length > 0:
            try:
                body_bytes = self.rfile.read(content_length)
                body_data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body_data = {}

        if path == "/api/tick":
            symbol = sanitize_symbol(body_data.get("symbol", ""))
            try:
                price = float(body_data.get("price", 0.0))
                volume = int(body_data.get("volume", 100))
            except (ValueError, TypeError):
                self._send_json(400, {"error": "Invalid numerical values for price or volume."})
                return

            if not symbol or price <= 0:
                self._send_json(400, {"error": "Valid 'symbol' and positive 'price' are required."})
                return

            tick = {
                "symbol": symbol,
                "price": price,
                "volume": volume,
                "timestamp": datetime.now(),
            }

            try:
                result = orchestrator.process_tick(tick)
                # Append activity log
                log_entry = {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "level": "INFO",
                    "category": "TICK",
                    "message": f"Tick ingested for {symbol}: ₹{price:.2f} (Vol: {volume}). Decision: {result.get('action') if result else 'Candle building'}",
                }
                server_logs = getattr(self.server, "activity_logs", None)
                if isinstance(server_logs, list):
                    server_logs.append(log_entry)
                    if len(server_logs) > 100:
                        server_logs.pop(0)

                self._send_json(200, {"status": "OK", "result": result, "tick": tick})
            except Exception as e:
                self._send_json(500, {"status": "ERROR", "message": str(e)})
            return

        if path == "/api/eod_exit":
            report = orchestrator.close_eod(datetime.now())
            log_entry = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": "ALERT",
                "category": "EOD",
                "message": "Market close trigger: Force square-off executed for all active IPO paper positions.",
            }
            server_logs = getattr(self.server, "activity_logs", None)
            if isinstance(server_logs, list):
                server_logs.append(log_entry)
            self._send_json(200, {"status": "CLOSED", "report": report})
            return

        if path in ("/api/ipos/select", "/api/select_ipo"):
            action = str(body_data.get("action", "select")).strip().lower()
            sym = sanitize_symbol(body_data.get("symbol", ""))
            c_name = str(body_data.get("company_name", "")).strip()[:100]
            try:
                issue_p = float(body_data.get("issue_price", 100.0))
            except (ValueError, TypeError):
                issue_p = 100.0

            if action == "deselect":
                if not sym:
                    self._send_json(400, {"error": "Symbol is required for deselect."})
                    return
                orchestrator.unregister_ipo(sym)
                msg = f"Manual Selection: {sym} ({c_name or sym}) removed from active trading candidates."
                server_logs = getattr(self.server, "activity_logs", None)
                if isinstance(server_logs, list):
                    server_logs.append({
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "level": "WARNING",
                        "category": "SELECTION",
                        "message": msg,
                    })
                self._send_json(200, {
                    "status": "OK",
                    "action": "deselected",
                    "symbol": sym,
                    "registered_ipos": orchestrator.registered_ipos,
                    "registered_symbols": list(orchestrator.brokers.keys()),
                })
                return

            ipo_payload = {
                "symbol": sym,
                "company_name": c_name or sym,
                "issue_price": issue_p,
            }
            try:
                registered_sym = orchestrator.register_ipo(ipo_payload)
                msg = f"Manual Selection: {registered_sym} ({c_name or registered_sym}) selected for listing-day trading from 13-Rule Matrix."
                server_logs = getattr(self.server, "activity_logs", None)
                if isinstance(server_logs, list):
                    server_logs.append({
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "level": "INFO",
                        "category": "SELECTION",
                        "message": msg,
                    })
                self._send_json(200, {
                    "status": "OK",
                    "action": "selected",
                    "symbol": registered_sym,
                    "registered_ipos": orchestrator.registered_ipos,
                    "registered_symbols": list(orchestrator.brokers.keys()),
                })
            except Exception as ex:
                self._send_json(500, {"status": "ERROR", "message": str(ex)})
        if path in ("/api/discover", "/api/sync_ipos"):
            server_logs = getattr(self.server, "activity_logs", None)

            def _run_discovery():
                try:
                    from backend.services.ipo_discovery_service import IPODiscoveryService
                    from backend.services.ipo_screening_runner import IPOScreeningRunner
                    if isinstance(server_logs, list):
                        server_logs.append({
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "level": "INFO",
                            "category": "DISCOVERY",
                            "message": "Connecting to Chittorgarh to scan live Mainboard IPOs...",
                        })
                    res = IPODiscoveryService().run()
                    if isinstance(server_logs, list):
                        server_logs.append({
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "level": "INFO",
                            "category": "DISCOVERY",
                            "message": f"Chittorgarh scan finished: {res.get('fetched', 0)} fetched, {res.get('inserted', 0)} new discoveries.",
                        })
                    screened = IPOScreeningRunner().screen_all()
                    if isinstance(server_logs, list):
                        server_logs.append({
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "level": "INFO",
                            "category": "SCREENING",
                            "message": f"13-Rule Institutional Screening evaluated {len(screened)} real IPOs.",
                        })
                except Exception as ex:
                    if isinstance(server_logs, list):
                        server_logs.append({
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "level": "ERROR",
                            "category": "DISCOVERY",
                            "message": f"Discovery/Screening failed: {ex}",
                        })

            threading.Thread(target=_run_discovery, name="LiveIPODiscoveryWorker", daemon=True).start()
            self._send_json(200, {"status": "STARTED", "message": "Live Chittorgarh discovery & screening initiated."})
            return

        self._send_json(404, {"error": f"POST '{path}' not supported."})


class IPOMonitoringServer:
    """
    Lightweight, production-hardened real-time monitoring web server for IPO trading.
    Enforces HTTP Basic Authorization, brute-force IP throttling, security headers, and optional SSL/TLS.
    """

    def __init__(
        self,
        orchestrator: Any,
        host: str = "127.0.0.1",
        port: int = 5050,
        auth_username: str | None = None,
        auth_password: str | None = None,
        ssl_certfile: str | None = None,
        ssl_keyfile: str | None = None,
        allowed_origins: list[str] | None = None,
        rate_limit_rpm: int | None = None,
    ):
        self.orchestrator = orchestrator
        self.host = host
        self.port = port
        self.auth_username = auth_username if auth_username is not None else DEFAULT_AUTH_USERNAME
        self.auth_password = auth_password if auth_password is not None else DEFAULT_AUTH_PASSWORD
        self.ssl_certfile = ssl_certfile or os.getenv("SSL_CERTFILE")
        self.ssl_keyfile = ssl_keyfile or os.getenv("SSL_KEYFILE")
        self.allowed_origins = allowed_origins
        effective_rpm = int(rate_limit_rpm) if rate_limit_rpm is not None else int(os.getenv("RATE_LIMIT_RPM", "1200"))
        self.rate_limiter = SecurityRateLimiter(max_rpm=effective_rpm)
        self.is_ssl = False
        self.httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.activity_logs: list[dict[str, Any]] = [
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": "INFO",
                "category": "SYSTEM",
                "message": "Master Listing Day Orchestrator initialized on NSE/BSE schedule.",
            },
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": "INFO",
                "category": "SAFETY",
                "message": "PaperBroker active. 100% Simulated Paper Trading Only. Real-money orders locked.",
            },
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": "INFO",
                "category": "SECURITY",
                "message": f"Authorization active: user '{self.auth_username}' authenticated.",
            },
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "level": "INFO",
                "category": "RISK",
                "message": "IPORiskManager circuit breakers engaged (Max Daily Loss / Max Positions / Max Capital per IPO).",
            },
        ]

    def start(self) -> None:
        """Start HTTP server in a background daemon thread with automatic port fallback and SSL/TLS wrapping."""
        if self.httpd is not None:
            return

        bind_port = self.port
        try:
            self.httpd = ThreadingHTTPServer((self.host, bind_port), IPOMonitoringHandler)
            self.port = self.httpd.server_port
        except OSError as exc:
            raise OSError(
                f"Failed to bind dashboard server to {self.host}:{bind_port}. "
                f"Port {bind_port} is already in use by another process. Details: {exc}"
            ) from exc

        # Wrap in TLS if certificate and key exist
        if self.ssl_certfile and self.ssl_keyfile:
            if os.path.exists(self.ssl_certfile) and os.path.exists(self.ssl_keyfile):
                import ssl
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(certfile=self.ssl_certfile, keyfile=self.ssl_keyfile)
                self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)
                self.is_ssl = True
                self.log_activity("INFO", "SECURITY", "TLS/HTTPS active. Public communication encrypted via SSL certificate.")

        # Warn if default credentials are used in exposed / public host binding
        if self.host not in ("127.0.0.1", "localhost") and (self.auth_username == "Anish_5337" and self.auth_password == "Anish_9482"):
            self.log_activity("WARNING", "SECURITY", "CRITICAL NOTICE: Server exposed on network with default credentials! Set custom AUTH_USERNAME and AUTH_PASSWORD in .env.")

        self.httpd.orchestrator = self.orchestrator  # type: ignore[attr-defined]
        self.httpd.activity_logs = self.activity_logs  # type: ignore[attr-defined]
        self.httpd.auth_username = self.auth_username  # type: ignore[attr-defined]
        self.httpd.auth_password = self.auth_password  # type: ignore[attr-defined]
        self.httpd.is_ssl = self.is_ssl  # type: ignore[attr-defined]
        self.httpd.rate_limiter = self.rate_limiter  # type: ignore[attr-defined]
        self.httpd.allowed_origins = self.allowed_origins  # type: ignore[attr-defined]

        self._thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="IPOMonitoringServerThread",
            daemon=True,
        )
        self._thread.start()

    def log_activity(self, level: str, category: str, message: str) -> None:
        """Append an operational log entry to the live backend event stream."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level.upper(),
            "category": category.upper(),
            "message": message,
        }
        self.activity_logs.append(entry)
        if len(self.activity_logs) > 200:
            self.activity_logs.pop(0)

    def stop(self) -> None:
        """Shutdown and close HTTP server."""
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self._thread = None
