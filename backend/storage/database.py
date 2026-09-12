import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "data"
DATABASE_FILE = DATABASE_DIR / "ipo_trading.db"


def get_connection() -> sqlite3.Connection:
    """Create and return a SQLite database connection."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    """Create the required database tables."""
    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                symbol TEXT,
                listing_date TEXT NOT NULL,
                issue_price REAL NOT NULL,
                issue_size REAL,
                sector TEXT,
                source TEXT NOT NULL,
                source_url TEXT,
                collected_at TEXT NOT NULL,

                UNIQUE(company_name, listing_date)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS listing_day_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                listing_date TEXT NOT NULL,
                listing_price REAL,
                opening_price REAL,
                high_price REAL,
                low_price REAL,
                closing_price REAL,
                volume INTEGER,
                source TEXT NOT NULL,
                source_url TEXT,
                collected_at TEXT NOT NULL,

                UNIQUE(symbol, listing_date)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                volume INTEGER,
                interval TEXT NOT NULL,
                source TEXT NOT NULL,

                UNIQUE(symbol, timestamp, interval)
            )
            """
        )
                # ---------------------------------------------------------
        # Candle table migrations
        # ---------------------------------------------------------
        candle_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(candles)"
            ).fetchall()
        }

        if "ipo_id" not in candle_columns:
            connection.execute(
                """
                ALTER TABLE candles
                ADD COLUMN ipo_id INTEGER
                """
            )

        if "provider_instrument_id" not in candle_columns:
            connection.execute(
                """
                ALTER TABLE candles
                ADD COLUMN provider_instrument_id TEXT
                """
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS instruments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                company_name TEXT NOT NULL,
                isin TEXT,
                exchange TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_instrument_id TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,

                UNIQUE(provider, provider_instrument_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipo_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ipo_id INTEGER NOT NULL UNIQUE,

                ipo_type TEXT,

                qib_subscription REAL,
                overall_subscription REAL,

                gmp_day_1 REAL,
                gmp_day_2 REAL,

                fresh_issue_percentage REAL,
                ofs_percentage REAL,

                anchor_investor_count INTEGER,

                sales_year_1 REAL,
                sales_year_2 REAL,
                sales_year_3 REAL,

                profit_year_1 REAL,
                profit_year_2 REAL,
                profit_year_3 REAL,

                margin_year_1 REAL,
                margin_year_2 REAL,
                margin_year_3 REAL,

                debt_previous REAL,
                debt_current REAL,

                roe REAL,
                roce REAL,

                ipo_pe REAL,
                peer_pe REAL,

                source TEXT,
                source_url TEXT,
                collected_at TEXT NOT NULL,

                FOREIGN KEY (ipo_id) REFERENCES ipos(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipo_rule_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ipo_id INTEGER NOT NULL,
                rule_number INTEGER NOT NULL,
                rule_name TEXT NOT NULL,
                actual_value TEXT,
                threshold TEXT,
                passed INTEGER NOT NULL,
                reason TEXT,
                evaluated_at TEXT NOT NULL,

                UNIQUE(ipo_id, rule_number),

                FOREIGN KEY (ipo_id) REFERENCES ipos(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipo_subscription_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ipo_id INTEGER NOT NULL,
                subscription_date TEXT NOT NULL,
                subscription_day INTEGER,
                qib_subscription REAL,
                nii_subscription REAL,
                retail_subscription REAL,
                overall_subscription REAL,
                total_applications INTEGER,
                source TEXT NOT NULL,
                source_url TEXT,
                collected_at TEXT NOT NULL,

                UNIQUE(
                    ipo_id,
                    subscription_date,
                    source
                ),

                FOREIGN KEY (ipo_id)
                    REFERENCES ipos(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipo_gmp_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ipo_id INTEGER NOT NULL,
                gmp_date TEXT NOT NULL,
                gmp_value REAL,
                gmp_percent REAL,
                estimated_listing_price REAL,
                source TEXT NOT NULL,
                source_url TEXT,
                collected_at TEXT NOT NULL,

                UNIQUE(
                    ipo_id,
                    gmp_date,
                    source
                ),

                FOREIGN KEY (ipo_id)
                    REFERENCES ipos(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipo_discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                chittorgarh_ipo_id INTEGER NOT NULL UNIQUE,

                company_name TEXT NOT NULL,
                ipo_type TEXT,

                ipo_open_date TEXT,
                ipo_close_date TEXT,
                listing_date TEXT,

                detail_url TEXT NOT NULL,

                status TEXT NOT NULL DEFAULT 'DISCOVERED',

                discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipo_screening_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                chittorgarh_ipo_id INTEGER NOT NULL,
                company_name TEXT NOT NULL,

                screened_at TEXT NOT NULL,

                strategy_result TEXT NOT NULL,
                status TEXT NOT NULL,

                passed INTEGER NOT NULL,
                failed INTEGER NOT NULL,
                not_evaluable INTEGER NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ipo_screening_rule_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                screening_run_id INTEGER NOT NULL,

                rule_number INTEGER NOT NULL,
                rule_name TEXT NOT NULL,

                status TEXT NOT NULL,
                passed INTEGER NOT NULL,

                actual_value TEXT,
                threshold TEXT,
                reason TEXT,

                FOREIGN KEY (
                    screening_run_id
                )
                REFERENCES ipo_screening_runs(id)
            )
            """
        )

        connection.commit()

    finally:
        connection.close()