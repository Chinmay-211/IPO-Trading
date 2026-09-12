from datetime import datetime

from backend.models.ipo_discovery import IPODiscovery
from backend.storage.database import get_connection


class IPODiscoveryRepository:
    """Database operations for discovered IPOs."""

    def add(self, discovery: IPODiscovery) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ipo_discoveries (
                    chittorgarh_ipo_id,
                    company_name,
                    ipo_type,
                    ipo_open_date,
                    ipo_close_date,
                    listing_date,
                    detail_url,
                    status,
                    discovered_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    discovery.chittorgarh_ipo_id,
                    discovery.company_name,
                    discovery.ipo_type,
                    discovery.ipo_open_date,
                    discovery.ipo_close_date,
                    discovery.listing_date,
                    discovery.detail_url,
                    discovery.status,
                    discovery.discovered_at,
                    discovery.updated_at,
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_by_chittorgarh_id(
        self,
        chittorgarh_ipo_id: int,
    ) -> dict | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM ipo_discoveries
                WHERE chittorgarh_ipo_id = ?
                LIMIT 1
                """,
                (chittorgarh_ipo_id,),
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
                FROM ipo_discoveries
                ORDER BY ipo_open_date DESC, id DESC
                """
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def get_by_status(
        self,
        status: str,
    ) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM ipo_discoveries
                WHERE status = ?
                ORDER BY ipo_open_date DESC, id DESC
                """,
                (status,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def update_status(
        self,
        chittorgarh_ipo_id: int,
        status: str,
    ) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                UPDATE ipo_discoveries
                SET status = ?,
                    updated_at = ?
                WHERE chittorgarh_ipo_id = ?
                """,
                (
                    status,
                    datetime.now().isoformat(),
                    chittorgarh_ipo_id,
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def reset_status(
        self,
        chittorgarh_ipo_id: int,
        status: str = "DISCOVERED",
    ) -> bool:
        """Reset one IPO to a screenable status."""

        allowed_statuses = {
            "DISCOVERED",
            "NOT_READY",
        }

        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid reset status: {status}"
            )

        return self.update_status(
            chittorgarh_ipo_id,
            status,
        )

    def reset_failed_to_discovered(self) -> int:
        """Reset all FAILED IPOs."""

        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                UPDATE ipo_discoveries
                SET status = ?,
                    updated_at = ?
                WHERE status = ?
                """,
                (
                    "DISCOVERED",
                    datetime.now().isoformat(),
                    "FAILED",
                ),
            )

            connection.commit()
            return cursor.rowcount

        finally:
            connection.close()

    def reset_screening_to_discovered(self) -> int:
        """
        Reset all previously screened IPOs.

        Includes:
            FAILED
            NOT_READY
            WATCHING
        """

        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                UPDATE ipo_discoveries
                SET status = ?,
                    updated_at = ?
                WHERE status IN (?, ?, ?)
                """,
                (
                    "DISCOVERED",
                    datetime.now().isoformat(),
                    "FAILED",
                    "NOT_READY",
                    "WATCHING",
                ),
            )

            connection.commit()
            return cursor.rowcount

        finally:
            connection.close()

    def delete_by_chittorgarh_id(
        self,
        chittorgarh_ipo_id: int,
    ) -> bool:
        """Delete a discovered IPO by Chittorgarh IPO ID."""

        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                DELETE FROM ipo_discoveries
                WHERE chittorgarh_ipo_id = ?
                """,
                (chittorgarh_ipo_id,),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def count(self) -> int:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM ipo_discoveries
                """
            ).fetchone()

            return row["count"]

        finally:
            connection.close()