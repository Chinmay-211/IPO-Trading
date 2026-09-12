from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)


def main():
    repository = IPODiscoveryRepository()

    ipo_id = 2574

    before = repository.get_by_chittorgarh_id(
        ipo_id
    )

    print("Before:")
    print(before)

    if before is None:
        print("IPO not found.")
        return

    changed = repository.reset_status(
        ipo_id,
        "DISCOVERED",
    )

    print()
    print("Reset:", changed)

    after = repository.get_by_chittorgarh_id(
        ipo_id
    )

    print()
    print("After:")
    print(after)


if __name__ == "__main__":
    main()