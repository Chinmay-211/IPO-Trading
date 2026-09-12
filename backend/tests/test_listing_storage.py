from datetime import date, datetime

from backend.models.listing import ListingDayData
from backend.storage.listing_repository import ListingRepository


def main():
    listing = ListingDayData(
        symbol="TESTLIST",
        listing_date=date(2026, 1, 2),
        listing_price=120.0,
        opening_price=125.0,
        high_price=130.0,
        low_price=118.0,
        closing_price=128.0,
        volume=100000,
        source="test",
        source_url=None,
        collected_at=datetime.now(),
    )

    repository = ListingRepository()

    inserted = repository.add(listing)

    print("Inserted:", inserted)
    print("Listing count:", repository.count())
    print("Records:")

    for record in repository.get_all():
        print(record)


if __name__ == "__main__":
    main()