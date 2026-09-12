from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)
from backend.services.ipo_screening_runner import (
    IPOScreeningRunner,
)
from backend.services.ipo_screening_summary import (
    IPOScreeningSummary,
)


def main():
    repository = IPODiscoveryRepository()

    # Reset previously screened IPOs so this test
    # performs exactly one complete screening run.
    reset_count = (
        repository.reset_failed_to_discovered()
    )

    print("Reset FAILED:", reset_count)

    runner = IPOScreeningRunner()

    results = runner.screen_all()

    summary = IPOScreeningSummary().build(
        results
    )

    print()
    print("=" * 50)
    print("IPO SCREENING SUMMARY")
    print("=" * 50)

    print("Total:", summary["total"])
    print("PASS:", summary["pass"])
    print("FAIL:", summary["fail"])
    print("NOT_READY:", summary["not_ready"])

    print()
    print("CANDIDATES")
    print("-" * 50)

    for candidate in summary["candidates"]:
        print(
            f"{candidate['company_name']} → "
            f"{candidate['passed']} PASS / "
            f"{candidate['failed']} FAIL / "
            f"{candidate['not_evaluable']} NOT_EVALUABLE"
        )


if __name__ == "__main__":
    main()