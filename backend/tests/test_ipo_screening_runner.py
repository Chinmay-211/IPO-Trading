from backend.services.ipo_screening_runner import (
    IPOScreeningRunner,
)


def main():
    runner = IPOScreeningRunner()

    results = runner.screen_all()

    print("=" * 60)
    print("IPO SCREENING RESULTS")
    print("=" * 60)

    print("Total:", len(results))

    for result in results:
        print()

        print(
            result["company_name"],
            "→",
            result.get("strategy_result", "UNKNOWN"),
        )

        if result.get("status") == "NOT_READY":
            print(
                "Reason:",
                result.get("error", "Unknown error"),
            )
            continue

        print(
            "Passed:",
            result.get("passed", 0),
            "Failed:",
            result.get("failed", 0),
            "Not evaluable:",
            result.get("not_evaluable", 0),
        )

if __name__ == "__main__":
    main()