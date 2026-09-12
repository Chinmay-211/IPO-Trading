from backend.storage.database import get_connection


class GMPRepository:
    """Database operations for IPO GMP snapshots."""

    def add(self, snapshot: dict) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ipo_gmp_snapshots (
                    ipo_id,
                    gmp_date,
                    gmp_value,
                    gmp_percent,
                    estimated_listing_price,
                    source,
                    source_url,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["ipo_id"],
                    snapshot["gmp_date"],
                    snapshot.get("gmp_value"),
                    snapshot.get("gmp_percent"),
                    snapshot.get("estimated_listing_price"),
                    snapshot["source"],
                    snapshot.get("source_url"),
                    snapshot["collected_at"],
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_by_ipo(self, ipo_id: int) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM ipo_gmp_snapshots
                WHERE ipo_id = ?
                ORDER BY gmp_date
                """,
                (ipo_id,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()
    def get_latest_two(self, ipo_id: int) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM ipo_gmp_snapshots
                WHERE ipo_id = ?
                ORDER BY gmp_date DESC
                LIMIT 2
                """,
                (ipo_id,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()