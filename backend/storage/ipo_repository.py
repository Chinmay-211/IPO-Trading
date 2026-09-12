from backend.models.ipo import IPO
from backend.storage.database import get_connection


class IPORepository:
    """Database operations for IPO records."""
    def get_by_company_name(
        self,
        company_name: str,
    ) -> dict | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM ipos
                WHERE company_name = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (company_name,),
            ).fetchone()

            return dict(row) if row else None

        finally:
            connection.close()

    def add(self, ipo: IPO) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ipos (
                    company_name,
                    symbol,
                    listing_date,
                    issue_price,
                    issue_size,
                    sector,
                    source,
                    source_url,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ipo.company_name,
                    ipo.symbol,
                    ipo.listing_date.isoformat(),
                    ipo.issue_price,
                    ipo.issue_size,
                    ipo.sector,
                    ipo.source,
                    ipo.source_url,
                    ipo.collected_at.isoformat(),
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_by_company_and_date(
        self,
        company_name: str,
        listing_date,
    ) -> dict | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM ipos
                WHERE company_name = ?
                  AND listing_date = ?
                LIMIT 1
                """,
                (
                    company_name,
                    listing_date.isoformat(),
                ),
            ).fetchone()

            return dict(row) if row else None

        finally:
            connection.close()

    def get_all(self) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM ipos
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
                "SELECT COUNT(*) AS count FROM ipos"
            ).fetchone()

            return row["count"]

        finally:
            connection.close()