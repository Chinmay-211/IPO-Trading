from datetime import datetime

from backend.storage.database import get_connection


class IPOScreeningRepository:
    """Persist IPO screening runs and rule results."""

    def save_run(
        self,
        result: dict,
    ) -> int:
        connection = get_connection()

        try:
            screened_at = datetime.now().isoformat()

            cursor = connection.execute(
                """
                INSERT INTO ipo_screening_runs (
                    chittorgarh_ipo_id,
                    company_name,
                    screened_at,
                    strategy_result,
                    status,
                    passed,
                    failed,
                    not_evaluable
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["chittorgarh_ipo_id"],
                    result["company_name"],
                    screened_at,
                    result["strategy_result"],
                    result["status"],
                    result.get("passed", 0),
                    result.get("failed", 0),
                    result.get("not_evaluable", 0),
                ),
            )

            screening_run_id = cursor.lastrowid

            for rule in result.get(
                "rule_results",
                [],
            ):
                connection.execute(
                    """
                    INSERT INTO ipo_screening_rule_results (
                        screening_run_id,
                        rule_number,
                        rule_name,
                        status,
                        passed,
                        actual_value,
                        threshold,
                        reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        screening_run_id,
                        rule.rule_number,
                        rule.rule_name,
                        rule.status,
                        int(rule.passed),
                        str(rule.actual_value),
                        str(rule.threshold),
                        rule.reason,
                    ),
                )

            connection.commit()

            return screening_run_id

        finally:
            connection.close()

    def get_latest_run(
        self,
        chittorgarh_ipo_id: int,
    ) -> dict | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM ipo_screening_runs
                WHERE chittorgarh_ipo_id = ?
                ORDER BY screened_at DESC, id DESC
                LIMIT 1
                """,
                (chittorgarh_ipo_id,),
            ).fetchone()

            return dict(row) if row else None

        finally:
            connection.close()

    def get_rule_results(
        self,
        screening_run_id: int,
    ) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM ipo_screening_rule_results
                WHERE screening_run_id = ?
                ORDER BY rule_number
                """,
                (screening_run_id,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def count_runs(self) -> int:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM ipo_screening_runs
                """
            ).fetchone()

            return row["count"]

        finally:
            connection.close()