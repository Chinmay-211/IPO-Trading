from dataclasses import dataclass
from datetime import datetime

from backend.models.ipo_analysis import IPOAnalysis


@dataclass
class RuleResult:
    rule_number: int
    rule_name: str
    actual_value: str
    threshold: str
    passed: bool
    reason: str
    evaluated_at: str
    status: str = "PASS"

    def __post_init__(self):
        if self.status not in {
            "PASS",
            "FAIL",
            "NOT_EVALUABLE",
        }:
            raise ValueError(
                "status must be PASS, FAIL, or NOT_EVALUABLE"
            )


class IPORuleEvaluator:
    """Evaluate all 13 defined IPO selection rules."""

    def evaluate(
        self,
        analysis: IPOAnalysis,
    ) -> list[RuleResult]:

        evaluated_at = datetime.utcnow().isoformat()

        return [
            self._rule_1(analysis, evaluated_at),
            self._rule_2(analysis, evaluated_at),
            self._rule_3(analysis, evaluated_at),
            self._rule_4(analysis, evaluated_at),
            self._rule_5(analysis, evaluated_at),
            self._rule_6(analysis, evaluated_at),
            self._rule_7(analysis, evaluated_at),
            self._rule_8(analysis, evaluated_at),
            self._rule_9(analysis, evaluated_at),
            self._rule_10(analysis, evaluated_at),
            self._rule_11(analysis, evaluated_at),
            self._rule_12(analysis, evaluated_at),
            self._rule_13(analysis, evaluated_at),
        ]

    # =========================================================
    # RULE 1
    # =========================================================

    def _rule_1(self, a, timestamp):

        if a.ipo_type is None:
            return self._not_evaluable(
                1,
                "Mainboard IPO",
                "None",
                "MAINBOARD",
                "IPO type is unavailable.",
                timestamp,
            )

        passed = (
            a.ipo_type.upper() == "MAINBOARD"
        )

        return self._result(
            1,
            "Mainboard IPO",
            str(a.ipo_type),
            "MAINBOARD",
            passed,
            "IPO must be Mainboard.",
            timestamp,
        )

    # =========================================================
    # RULE 2
    # =========================================================

    def _rule_2(self, a, timestamp):

        if a.qib_subscription is None:
            return self._not_evaluable(
                2,
                "QIB Subscription",
                "None",
                ">= 20x",
                "QIB subscription data is unavailable.",
                timestamp,
            )

        passed = a.qib_subscription >= 20

        return self._result(
            2,
            "QIB Subscription",
            str(a.qib_subscription),
            ">= 20x",
            passed,
            "QIB subscription must be at least 20x.",
            timestamp,
        )

    # =========================================================
    # RULE 3
    # =========================================================

    def _rule_3(self, a, timestamp):

        if a.overall_subscription is None:
            return self._not_evaluable(
                3,
                "Overall Subscription",
                "None",
                ">= 15x",
                "Overall subscription data is unavailable.",
                timestamp,
            )

        passed = a.overall_subscription >= 15

        return self._result(
            3,
            "Overall Subscription",
            str(a.overall_subscription),
            ">= 15x",
            passed,
            "Overall subscription must be at least 15x.",
            timestamp,
        )

    # =========================================================
    # RULE 4
    # =========================================================

    def _rule_4(self, a, timestamp):

        actual = (
            f"{a.gmp_day_1}%, "
            f"{a.gmp_day_2}%"
        )

        if (
            a.gmp_day_1 is None
            or a.gmp_day_2 is None
        ):
            return self._not_evaluable(
                4,
                "GMP",
                actual,
                ">= 10% for both days",
                "One or both required GMP values are unavailable.",
                timestamp,
            )

        passed = (
            a.gmp_day_1 >= 10
            and a.gmp_day_2 >= 10
        )

        return self._result(
            4,
            "GMP",
            actual,
            ">= 10% for both days",
            passed,
            "GMP must be at least 10% on both specified days.",
            timestamp,
        )

    # =========================================================
    # RULE 5
    # =========================================================

    def _rule_5(self, a, timestamp):

        if a.fresh_issue_percentage is None:
            return self._not_evaluable(
                5,
                "Fresh Issue",
                "None%",
                ">= 70%",
                "Fresh issue percentage is unavailable.",
                timestamp,
            )

        passed = (
            a.fresh_issue_percentage >= 70
        )

        return self._result(
            5,
            "Fresh Issue",
            f"{a.fresh_issue_percentage}%",
            ">= 70%",
            passed,
            "Fresh issue must be at least 70%.",
            timestamp,
        )

    # =========================================================
    # RULE 6
    # =========================================================

    def _rule_6(self, a, timestamp):

        if a.anchor_investor_count is None:
            return self._not_evaluable(
                6,
                "Anchor Investors",
                "None",
                ">= 5",
                "Anchor investor data is unavailable.",
                timestamp,
            )

        passed = (
            a.anchor_investor_count >= 5
        )

        return self._result(
            6,
            "Anchor Investors",
            str(a.anchor_investor_count),
            ">= 5",
            passed,
            "IPO must have at least 5 anchor investors.",
            timestamp,
        )

    # =========================================================
    # RULE 7
    # =========================================================

    def _rule_7(self, a, timestamp):

        actual = (
            f"{a.sales_year_1}, "
            f"{a.sales_year_2}, "
            f"{a.sales_year_3}"
        )

        if (
            a.sales_year_1 is None
            or a.sales_year_2 is None
            or a.sales_year_3 is None
        ):
            return self._not_evaluable(
                7,
                "Sales Growth",
                actual,
                "Consistently increasing for 3 years",
                "Three years of sales data are required.",
                timestamp,
            )

        passed = (
            a.sales_year_1 < a.sales_year_2
            and a.sales_year_2 < a.sales_year_3
        )

        return self._result(
            7,
            "Sales Growth",
            actual,
            "Consistently increasing for 3 years",
            passed,
            "Sales must increase year-over-year for all 3 years.",
            timestamp,
        )

    # =========================================================
    # RULE 8
    # =========================================================

    def _rule_8(self, a, timestamp):

        actual = (
            f"{a.profit_year_1}, "
            f"{a.profit_year_2}, "
            f"{a.profit_year_3}"
        )

        if (
            a.profit_year_1 is None
            or a.profit_year_2 is None
            or a.profit_year_3 is None
        ):
            return self._not_evaluable(
                8,
                "Profit Growth",
                actual,
                "Consistently increasing for 3 years",
                "Three years of profit data are required.",
                timestamp,
            )

        passed = (
            a.profit_year_1 < a.profit_year_2
            and a.profit_year_2 < a.profit_year_3
        )

        return self._result(
            8,
            "Profit Growth",
            actual,
            "Consistently increasing for 3 years",
            passed,
            "Profit must increase year-over-year for all 3 years.",
            timestamp,
        )

    # =========================================================
    # RULE 9
    # =========================================================

    def _rule_9(self, a, timestamp):

        actual = (
            f"{self._format_percent(a.margin_year_1)}, "
            f"{self._format_percent(a.margin_year_2)}, "
            f"{self._format_percent(a.margin_year_3)}"
        )

        if (
            a.margin_year_1 is None
            or a.margin_year_2 is None
            or a.margin_year_3 is None
        ):
            return self._not_evaluable(
                9,
                "Profit Margin",
                actual,
                "Consistently increasing for 3 years",
                "Three years of profit-margin data are required.",
                timestamp,
            )

        passed = (
            a.margin_year_1 < a.margin_year_2
            and a.margin_year_2 < a.margin_year_3
        )

        return self._result(
            9,
            "Profit Margin",
            actual,
            "Consistently increasing for 3 years",
            passed,
            "Profit margin must increase year-over-year for all 3 years.",
            timestamp,
        )

    # =========================================================
    # RULE 10
    # =========================================================

    def _rule_10(self, a, timestamp):

        actual = (
            f"Previous={a.debt_previous}, "
            f"Current={a.debt_current}"
        )

        if (
            a.debt_previous is None
            or a.debt_current is None
        ):
            return self._not_evaluable(
                10,
                "Debt",
                actual,
                "Decreasing OR increase <= 6%",
                "Required debt data is unavailable.",
                timestamp,
            )

        if a.debt_previous < 0:
            return self._not_evaluable(
                10,
                "Debt",
                actual,
                "Decreasing OR increase <= 6%",
                "Previous debt value is invalid.",
                timestamp,
            )

        if a.debt_current <= a.debt_previous:
            passed = True

        elif a.debt_previous > 0:
            increase = (
                (
                    a.debt_current
                    - a.debt_previous
                )
                / a.debt_previous
                * 100
            )

            passed = increase <= 6

        else:
            passed = False

        return self._result(
            10,
            "Debt",
            actual,
            "Decreasing OR increase <= 6%",
            passed,
            "Debt must decrease or increase by no more than 6%.",
            timestamp,
        )

    # =========================================================
    # RULE 11
    # =========================================================

    def _rule_11(self, a, timestamp):

        actual = (
            f"ROE={a.roe}%, "
            f"ROCE={a.roce}%"
        )

        if (
            a.roe is None
            or a.roce is None
        ):
            return self._not_evaluable(
                11,
                "ROE / ROCE",
                actual,
                "Both > 10%",
                "ROE and ROCE data are required.",
                timestamp,
            )

        passed = (
            a.roe > 10
            and a.roce > 10
        )

        return self._result(
            11,
            "ROE / ROCE",
            actual,
            "Both > 10%",
            passed,
            "Both ROE and ROCE must be above 10%.",
            timestamp,
        )

    # =========================================================
    # RULE 12
    # =========================================================

    def _rule_12(self, a, timestamp):

        if a.peer_pe is None:
            return self._not_evaluable(
                12,
                "Valuation vs Peer",
                f"IPO P/E={a.ipo_pe}, Peer P/E=None",
                "Reasonable vs directly comparable peer",
                "No directly comparable peer valuation is available.",
                timestamp,
            )

        if a.ipo_pe is None:
            return self._not_evaluable(
                12,
                "Valuation vs Peer",
                f"IPO P/E=None, Peer P/E={a.peer_pe}",
                "Reasonable vs directly comparable peer",
                "IPO P/E is unavailable.",
                timestamp,
            )

        return self._not_evaluable(
            12,
            "Valuation vs Peer",
            f"IPO P/E={a.ipo_pe}, Peer P/E={a.peer_pe}",
            "Reasonable vs directly comparable peer",
            "Peer valuation exists, but no numerical acceptable valuation difference is defined.",
            timestamp,
        )

    # =========================================================
    # RULE 13
    # =========================================================

    def _rule_13(self, a, timestamp):

        if a.ipo_pe is None:
            return self._not_evaluable(
                13,
                "P/E Ratio",
                "None",
                "15 <= P/E <= 50",
                "IPO P/E is unavailable.",
                timestamp,
            )

        passed = (
            15 <= a.ipo_pe <= 50
        )

        return self._result(
            13,
            "P/E Ratio",
            str(a.ipo_pe),
            "15 <= P/E <= 50",
            passed,
            "P/E must be between 15 and 50.",
            timestamp,
        )

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _result(
        rule_number: int,
        rule_name: str,
        actual_value: str,
        threshold: str,
        passed: bool,
        reason: str,
        timestamp: str,
    ) -> RuleResult:

        return RuleResult(
            rule_number=rule_number,
            rule_name=rule_name,
            actual_value=actual_value,
            threshold=threshold,
            passed=passed,
            reason=reason,
            evaluated_at=timestamp,
            status="PASS" if passed else "FAIL",
        )

    @staticmethod
    def _not_evaluable(
        rule_number: int,
        rule_name: str,
        actual_value: str,
        threshold: str,
        reason: str,
        timestamp: str,
    ) -> RuleResult:

        return RuleResult(
            rule_number=rule_number,
            rule_name=rule_name,
            actual_value=actual_value,
            threshold=threshold,
            passed=False,
            reason=reason,
            evaluated_at=timestamp,
            status="NOT_EVALUABLE",
        )

    @staticmethod
    def _format_percent(value) -> str:

        if value is None:
            return "None%"

        return f"{value:.2f}%"