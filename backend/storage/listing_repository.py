from backend.models.listing import ListingDayData
from backend.storage.database import get_connection


class ListingRepository:
    """Database operations for listing-day data."""

    def add(self, listing: ListingDayData) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO listing_day_data (
                    symbol,
                    listing_date,
                    listing_price,
                    opening_price,
                    high_price,
                    low_price,
                    closing_price,
                    volume,
                    source,
                    source_url,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    listing.symbol,
                    listing.listing_date.isoformat(),
                    listing.listing_price,
                    listing.opening_price,
                    listing.high_price,
                    listing.low_price,
                    listing.closing_price,
                    listing.volume,
                    listing.source,
                    listing.source_url,
                    listing.collected_at.isoformat(),
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_all(self) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM listing_day_data
                ORDER BY listing_date
                """
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def count(self) -> int:
        connection = get_connection()

        try:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM listing_day_data"
            ).fetchone()

            return row["count"]

        finally:
            connection.close()