from datetime import datetime

from backend.models.ipo_analysis import IPOAnalysis
from backend.storage.database import get_connection


class IPOAnalysisRepository:
    """Repository for IPO fundamental and subscription analysis data."""

    def insert(self, analysis: IPOAnalysis) -> bool:
        connection = get_connection()

        try:
            cursor = connection.execute(
                """
                INSERT OR REPLACE INTO ipo_analysis (
                    ipo_id,
                    ipo_type,
                    qib_subscription,
                    overall_subscription,
                    gmp_day_1,
                    gmp_day_2,
                    fresh_issue_percentage,
                    ofs_percentage,
                    anchor_investor_count,
                    sales_year_1,
                    sales_year_2,
                    sales_year_3,
                    profit_year_1,
                    profit_year_2,
                    profit_year_3,
                    margin_year_1,
                    margin_year_2,
                    margin_year_3,
                    debt_previous,
                    debt_current,
                    roe,
                    roce,
                    ipo_pe,
                    peer_pe,
                    source,
                    source_url,
                    collected_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    analysis.ipo_id,
                    analysis.ipo_type,
                    analysis.qib_subscription,
                    analysis.overall_subscription,
                    analysis.gmp_day_1,
                    analysis.gmp_day_2,
                    analysis.fresh_issue_percentage,
                    analysis.ofs_percentage,
                    analysis.anchor_investor_count,
                    analysis.sales_year_1,
                    analysis.sales_year_2,
                    analysis.sales_year_3,
                    analysis.profit_year_1,
                    analysis.profit_year_2,
                    analysis.profit_year_3,
                    analysis.margin_year_1,
                    analysis.margin_year_2,
                    analysis.margin_year_3,
                    analysis.debt_previous,
                    analysis.debt_current,
                    analysis.roe,
                    analysis.roce,
                    analysis.ipo_pe,
                    analysis.peer_pe,
                    analysis.source,
                    analysis.source_url,
                    analysis.collected_at,
                ),
            )

            connection.commit()
            return cursor.rowcount > 0

        finally:
            connection.close()

    def get_by_ipo_id(self, ipo_id: int) -> dict | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM ipo_analysis
                WHERE ipo_id = ?
                """,
                (ipo_id,),
            ).fetchone()

            return dict(row) if row else None

        finally:
            connection.close()

    def count(self) -> int:
        connection = get_connection()

        try:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM ipo_analysis"
            ).fetchone()

            return row["count"]

        finally:
            connection.close()