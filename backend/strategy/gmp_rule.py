class GMPRule:
    """Evaluate the GMP requirement for an IPO."""

    def __init__(self, minimum_percent: float = 10.0):
        self.minimum_percent = minimum_percent

    def evaluate(self, snapshots: list[dict]) -> dict:
        if len(snapshots) < 2:
            return {
                "passed": False,
                "reason": "Insufficient GMP history",
            }

        # Use the two latest GMP observations.
        latest = sorted(
            snapshots,
            key=lambda x: x["gmp_date"],
            reverse=True,
        )[:2]

        percentages = [
            snapshot["gmp_percent"]
            for snapshot in latest
        ]

        if any(value is None for value in percentages):
            return {
                "passed": False,
                "reason": "GMP percentage unavailable",
            }

        passed = all(
            value > self.minimum_percent
            for value in percentages
        )

        return {
            "passed": passed,
            "reason": (
                "GMP above minimum on both latest days"
                if passed
                else "GMP did not exceed minimum on both latest days"
            ),
            "days_checked": len(latest),
            "gmp_percentages": percentages,
            "minimum_percent": self.minimum_percent,
        }