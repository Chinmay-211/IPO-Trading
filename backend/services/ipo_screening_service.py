from backend.storage.ipo_analysis_repository import (
    IPOAnalysisRepository,
)
from backend.storage.ipo_repository import IPORepository
from backend.storage.ipo_rule_repository import (
    IPORuleRepository,
)
from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)
from backend.strategy.ipo_rule_evaluator import (
    IPORuleEvaluator,
)


class IPOScreeningService:
    """Orchestrate IPO analysis and 13-rule screening."""

    def __init__(
        self,
        ipo_repository=None,
        analysis_repository=None,
        rule_repository=None,
        analysis_builder=None,
        rule_evaluator=None,
    ):
        self.ipo_repository = (
            ipo_repository or IPORepository()
        )

        self.analysis_repository = (
            analysis_repository
            or IPOAnalysisRepository()
        )

        self.rule_repository = (
            rule_repository
            or IPORuleRepository()
        )

        self.analysis_builder = (
            analysis_builder
            or IPOAnalysisBuilder()
        )

        self.rule_evaluator = (
            rule_evaluator
            or IPORuleEvaluator()
        )

    def screen_ipo(
        self,
        *,
        internal_ipo_id: int,
        chittorgarh_ipo_id: int,
        chittorgarh_url: str,
        company_name: str,
        ipo_type: str,
    ) -> dict:

        analysis = self.analysis_builder.build(
            ipo_id=internal_ipo_id,
            chittorgarh_ipo_id=chittorgarh_ipo_id,
            chittorgarh_url=chittorgarh_url,
            company_name=company_name,
            ipo_type=ipo_type,
        )

        self.analysis_repository.insert(
            analysis
        )

        results = self.rule_evaluator.evaluate(
            analysis
        )

        self.rule_repository.save_results(
            internal_ipo_id,
            results,
        )

        passed = sum(
            1
            for result in results
            if result.status == "PASS"
        )

        failed = sum(
            1
            for result in results
            if result.status == "FAIL"
        )

        not_evaluable = sum(
            1
            for result in results
            if result.status == "NOT_EVALUABLE"
        )

        strategy_pass = (
            len(results) == 13
            and passed == 13
        )

        return {
            "ipo_id": internal_ipo_id,
            "company_name": company_name,
            "analysis": analysis,
            "rule_results": results,
            "total_rules": len(results),
            "passed": passed,
            "failed": failed,
            "not_evaluable": not_evaluable,
            "strategy_result": (
                "PASS"
                if strategy_pass
                else "FAIL"
            ),
        }