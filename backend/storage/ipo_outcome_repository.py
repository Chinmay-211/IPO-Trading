from backend.storage.database import get_connection


class IPOOutcomeRepository:
    """Database operations for historical IPO listing outcomes."""

    def save_listing_day_data(
        self,
        symbol: str,
        listing_date: str,
        listing_price: float | None,
        opening_price: float | None,
        high_price: float | None,
        low_price: float | None,
        closing_price: float | None,
        volume: int | None,
        source: str,
        source_url: str | None,
        collected_at: str,
    ) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR REPLACE INTO listing_day_data (
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
                    collected_at,
                ),
            )

            connection.commit()

            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_listing_day_data(
        self,
        symbol: str,
        listing_date: str,
    ) -> dict | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM listing_day_data
                WHERE symbol = ?
                  AND listing_date = ?
                LIMIT 1
                """,
                (
                    symbol,
                    listing_date,
                ),
            ).fetchone()

            return dict(row) if row else None

        finally:
            connection.close()

    def calculate_listing_gain(
        self,
        listing_price: float | None,
        issue_price: float | None,
    ) -> float | None:
        if (
            listing_price is None
            or issue_price is None
            or issue_price <= 0
        ):
            return None

        return (
            (listing_price - issue_price)
            / issue_price
            * 100
        )

    def calculate_opening_gain(
        self,
        opening_price: float | None,
        listing_price: float | None,
    ) -> float | None:
        if (
            opening_price is None
            or listing_price is None
            or listing_price <= 0
        ):
            return None

        return (
            (opening_price - listing_price)
            / listing_price
            * 100
        )

    def calculate_intraday_high_gain(
        self,
        high_price: float | None,
        opening_price: float | None,
    ) -> float | None:
        if (
            high_price is None
            or opening_price is None
            or opening_price <= 0
        ):
            return None

        return (
            (high_price - opening_price)
            / opening_price
            * 100
        )

    def calculate_intraday_low_drawdown(
        self,
        low_price: float | None,
        opening_price: float | None,
    ) -> float | None:
        if (
            low_price is None
            or opening_price is None
            or opening_price <= 0
        ):
            return None

        return (
            (low_price - opening_price)
            / opening_price
            * 100
        )

    def calculate_close_return(
        self,
        closing_price: float | None,
        opening_price: float | None,
    ) -> float | None:
        if (
            closing_price is None
            or opening_price is None
            or opening_price <= 0
        ):
            return None

        return (
            (closing_price - opening_price)
            / opening_price
            * 100
        )