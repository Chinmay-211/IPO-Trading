class IPOScreeningSummary:
    """Build a compact summary from one screening run."""

    def build(self, results: list[dict]) -> dict:
        total = len(results)

        passed = [
            result
            for result in results
            if result.get("strategy_result") == "PASS"
        ]

        failed = [
            result
            for result in results
            if result.get("strategy_result") == "FAIL"
        ]

        not_ready = [
            result
            for result in results
            if result.get("strategy_result") == "NOT_READY"
        ]

        candidates = sorted(
            passed,
            key=lambda result: (
                -result.get("passed", 0),
                result.get("not_evaluable", 0),
            ),
        )

        return {
            "total": total,
            "pass": len(passed),
            "fail": len(failed),
            "not_ready": len(not_ready),
            "candidates": [
                {
                    "company_name": result["company_name"],
                    "chittorgarh_ipo_id": (
                        result["chittorgarh_ipo_id"]
                    ),
                    "passed": result.get("passed", 0),
                    "failed": result.get("failed", 0),
                    "not_evaluable": result.get(
                        "not_evaluable", 0
                    ),
                }
                for result in candidates
            ],
        }