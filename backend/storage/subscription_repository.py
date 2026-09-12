from backend.storage.database import get_connection


class SubscriptionRepository:
    """Store IPO subscription snapshots."""

    def add(self, snapshot: dict) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ipo_subscription_snapshots (
                    ipo_id,
                    subscription_date,
                    subscription_day,
                    qib_subscription,
                    nii_subscription,
                    retail_subscription,
                    overall_subscription,
                    total_applications,
                    source,
                    source_url,
                    collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["ipo_id"],
                    snapshot["subscription_date"],
                    snapshot.get("subscription_day"),
                    snapshot.get("qib_subscription"),
                    snapshot.get("nii_subscription"),
                    snapshot.get("retail_subscription"),
                    snapshot.get("overall_subscription"),
                    snapshot.get("total_applications"),
                    snapshot["source"],
                    snapshot.get("source_url"),
                    snapshot["collected_at"],
                ),
            )

            connection.commit()

            return cursor.rowcount > 0

        finally:
            connection.close()