from backend.storage.database import get_connection
from backend.strategy.ipo_rule_evaluator import RuleResult


class IPORuleRepository:
    """Repository for IPO rule evaluation results."""

    def save_results(
        self,
        ipo_id: int,
        results: list[RuleResult],
    ) -> int:
        connection = get_connection()

        try:
            saved = 0

            for result in results:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO ipo_rule_results (
                        ipo_id,
                        rule_number,
                        rule_name,
                        actual_value,
                        threshold,
                        passed,
                        reason,
                        evaluated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ipo_id,
                        result.rule_number,
                        result.rule_name,
                        result.actual_value,
                        result.threshold,
                        int(result.passed),
                        result.reason,
                        result.evaluated_at,
                    ),
                )

                saved += 1

            connection.commit()
            return saved

        finally:
            connection.close()

    def get_results(self, ipo_id: int) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT
                    rule_number,
                    rule_name,
                    actual_value,
                    threshold,
                    passed,
                    reason,
                    evaluated_at
                FROM ipo_rule_results
                WHERE ipo_id = ?
                ORDER BY rule_number
                """,
                (ipo_id,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def count_passed(self, ipo_id: int) -> int:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM ipo_rule_results
                WHERE ipo_id = ?
                  AND passed = 1
                """,
                (ipo_id,),
            ).fetchone()

            return row["count"]

        finally:
            connection.close()