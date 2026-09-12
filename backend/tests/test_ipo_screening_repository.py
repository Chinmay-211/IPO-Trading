from backend.storage.database import (
    initialize_database,
)
from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)
from backend.storage.ipo_screening_repository import (
    IPOScreeningRepository,
)


def main():
    initialize_database()

    discovery_repository = (
        IPODiscoveryRepository()
    )

    screening_repository = (
        IPOScreeningRepository()
    )

    discovery = (
        discovery_repository.get_by_chittorgarh_id(
            2574
        )
    )

    if discovery is None:
        print("Lohia Corp not found.")
        return

    latest = (
        screening_repository.get_latest_run(
            2574
        )
    )

    print("Latest screening run:")
    print(latest)

    if latest is None:
        print("No screening run found.")
        return

    rules = (
        screening_repository.get_rule_results(
            latest["id"]
        )
    )

    print()
    print("Stored rule results:", len(rules))

    for rule in rules:
        print(
            f"Rule {rule['rule_number']}: "
            f"{rule['rule_name']} → "
            f"{rule['status']}"
        )

    print()
    print(
        "Total stored runs:",
        screening_repository.count_runs(),
    )


if __name__ == "__main__":
    main()