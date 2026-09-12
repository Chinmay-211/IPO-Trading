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