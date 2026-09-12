from backend.models.ipo_discovery import IPODiscovery
from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)


def main():
    discovery = IPODiscovery(
        chittorgarh_ipo_id=999999,
        company_name="TEST DISCOVERY IPO",
        ipo_type="MAINBOARD",
        ipo_open_date="25-Aug-2026",
        ipo_close_date="28-Aug-2026",
        listing_date=None,
        detail_url=(
            "https://www.chittorgarh.com/ipo/"
            "test-discovery-ipo/999999/"
        ),
    )

    repository = IPODiscoveryRepository()

    inserted = repository.add(discovery)

    print("Inserted:", inserted)
    print("Count:", repository.count())

    print("Record:")
    print(
        repository.get_by_chittorgarh_id(
            999999
        )
    )

    print("DISCOVERED records:")
    for record in repository.get_by_status(
        "DISCOVERED"
    ):
        print(record)


if __name__ == "__main__":
    main()