from datetime import datetime

from backend.storage.database import get_connection


class IPOCandleRepository:
    """Database operations for IPO listing-day intraday candles."""

    @staticmethod
    def _normalize_listing_date(listing_date: str) -> str:
        """
        Convert supported listing-date formats into YYYY-MM-DD.

        Examples:
            2026-08-24
            24-Aug-2026
            24-AUG-2026
        """
        if not listing_date:
            raise ValueError("listing_date is required.")

        listing_date = str(listing_date).strip()

        # Already ISO formatted.
        try:
            return datetime.strptime(
                listing_date,
                "%Y-%m-%d",
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass

        # Chittorgarh format.
        try:
            return datetime.strptime(
                listing_date,
                "%d-%b-%Y",
            ).strftime("%Y-%m-%d")
        except ValueError:
            pass

        raise ValueError(
            f"Unsupported listing date format: {listing_date}"
        )

    def save_candle(
        self,
        symbol: str,
        timestamp: str,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: int | None,
        interval: str,
        source: str,
        ipo_id: int | None = None,
        provider_instrument_id: str | None = None,
    ) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                UPDATE candles
                SET
                    open_price = ?,
                    high_price = ?,
                    low_price = ?,
                    close_price = ?,
                    volume = ?,
                    source = ?,
                    ipo_id = ?,
                    provider_instrument_id = ?
                WHERE symbol = ?
                  AND timestamp = ?
                  AND interval = ?
                """,
                (
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    source,
                    ipo_id,
                    provider_instrument_id,
                    symbol,
                    timestamp,
                    interval,
                ),
            )

            if cursor.rowcount > 0:
                connection.commit()
                return True

            cursor = connection.execute(
                """
                INSERT INTO candles (
                    symbol,
                    timestamp,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    interval,
                    source,
                    ipo_id,
                    provider_instrument_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    timestamp,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    interval,
                    source,
                    ipo_id,
                    provider_instrument_id,
                ),
            )

            connection.commit()

            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_candles(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "1m",
    ) -> list[dict]:
        normalized_date = self._normalize_listing_date(
            listing_date
        )

        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM candles
                WHERE symbol = ?
                                    AND substr(timestamp, 1, 10) = ?
                  AND interval = ?
                ORDER BY timestamp ASC
                """,
                (
                    symbol,
                                        normalized_date,
                    interval,
                ),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def get_candles_by_ipo(
        self,
        ipo_id: int,
        listing_date: str,
        interval: str = "1m",
    ) -> list[dict]:
        """
        Return all candles belonging to an IPO on its listing day.

        Candle timestamps are stored in ISO format, e.g.:

            2026-08-24T10:00:00+05:30

        Therefore the listing date is normalized to YYYY-MM-DD
        before applying the range query.
        """
        normalized_date = self._normalize_listing_date(
            listing_date
        )

        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM candles
                WHERE ipo_id = ?
                                    AND substr(timestamp, 1, 10) = ?
                  AND interval = ?
                ORDER BY timestamp ASC
                """,
                (
                    ipo_id,
                                        normalized_date,
                    interval,
                ),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def get_first_candle(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "1m",
    ) -> dict | None:
        candles = self.get_candles(
            symbol=symbol,
            listing_date=listing_date,
            interval=interval,
        )

        return candles[0] if candles else None

    def get_last_candle(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "1m",
    ) -> dict | None:
        candles = self.get_candles(
            symbol=symbol,
            listing_date=listing_date,
            interval=interval,
        )

        return candles[-1] if candles else None

    def count_candles(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "1m",
    ) -> int:
        return len(
            self.get_candles(
                symbol=symbol,
                listing_date=listing_date,
                interval=interval,
            )
        )

    def count_candles_by_ipo(
        self,
        ipo_id: int,
        listing_date: str,
        interval: str = "1m",
    ) -> int:
        return len(
            self.get_candles_by_ipo(
                ipo_id=ipo_id,
                listing_date=listing_date,
                interval=interval,
            )
        )