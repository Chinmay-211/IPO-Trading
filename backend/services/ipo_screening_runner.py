from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)
from backend.storage.ipo_screening_repository import (
    IPOScreeningRepository,
)
from backend.strategy.ipo_analysis_builder import (
    IPOAnalysisBuilder,
)
from backend.strategy.ipo_rule_evaluator import (
    IPORuleEvaluator,
)


class IPOScreeningRunner:
    """
    Screen persisted Chittorgarh IPO discoveries.

    Lifecycle:

        DISCOVERED
            ↓
        ANALYZING
            ↓
        WATCHING / FAILED / NOT_READY

    Every completed screening run is also persisted.
    """

    def __init__(
        self,
        discovery_repository=None,
        analysis_builder=None,
        rule_evaluator=None,
        screening_repository=None,
    ):
        self.discovery_repository = (
            discovery_repository
            or IPODiscoveryRepository()
        )

        self.analysis_builder = (
            analysis_builder
            or IPOAnalysisBuilder()
        )

        self.rule_evaluator = (
            rule_evaluator
            or IPORuleEvaluator()
        )

        self.screening_repository = (
            screening_repository
            or IPOScreeningRepository()
        )

    def screen_all(self) -> list[dict]:
        """Screen all discovered IPOs."""

        discoveries = (
            self.discovery_repository.get_by_status(
                "DISCOVERED"
            )
            + self.discovery_repository.get_by_status(
                "NOT_READY"
            )
        )

        results = []

        for discovery in discoveries:
            results.append(
                self.screen_discovery(discovery)
            )

        return results

    def screen_discovery(
        self,
        discovery: dict,
    ) -> dict:

        chittorgarh_ipo_id = discovery[
            "chittorgarh_ipo_id"
        ]

        company_name = discovery[
            "company_name"
        ]

        detail_url = discovery[
            "detail_url"
        ]

        ipo_type = discovery.get(
            "ipo_type"
        )

        self.discovery_repository.update_status(
            chittorgarh_ipo_id,
            "ANALYZING",
        )

        try:
            analysis = self.analysis_builder.build(
                ipo_id=chittorgarh_ipo_id,
                chittorgarh_url=detail_url,
                chittorgarh_ipo_id=chittorgarh_ipo_id,
                company_name=company_name,
                symbol=None,
                ipo_type=ipo_type,
            )

            rule_results = (
                self.rule_evaluator.evaluate(
                    analysis
                )
            )

            passed = sum(
                1
                for result in rule_results
                if result.status == "PASS"
            )

            failed = sum(
                1
                for result in rule_results
                if result.status == "FAIL"
            )

            not_evaluable = sum(
                1
                for result in rule_results
                if result.status == "NOT_EVALUABLE"
            )

            if failed > 0:
                strategy_result = "FAIL"
                status = "FAILED"

            elif (
                passed + not_evaluable == 13
                and len(rule_results) == 13
            ):
                strategy_result = "PASS"
                status = "WATCHING"

            else:
                strategy_result = "NOT_READY"
                status = "NOT_READY"

            self.discovery_repository.update_status(
                chittorgarh_ipo_id,
                status,
            )

            result = {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "strategy_result": strategy_result,
                "status": status,
                "passed": passed,
                "failed": failed,
                "not_evaluable": not_evaluable,
                "rule_results": rule_results,
                "analysis": analysis,
            }

            self.screening_repository.save_run(
                result
            )

            return result

        except Exception as exc:

            self.discovery_repository.update_status(
                chittorgarh_ipo_id,
                "NOT_READY",
            )

            result = {
                "company_name": company_name,
                "chittorgarh_ipo_id": (
                    chittorgarh_ipo_id
                ),
                "strategy_result": "NOT_READY",
                "status": "NOT_READY",
                "passed": 0,
                "failed": 0,
                "not_evaluable": 0,
                "rule_results": [],
                "error": str(exc),
            }

            self.screening_repository.save_run(
                result
            )

            return result