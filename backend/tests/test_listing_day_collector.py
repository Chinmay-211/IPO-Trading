from datetime import date

from backend.collectors.listing.listing_day_collector import (
    ListingDayCollector,
)


def main():
    collector = ListingDayCollector()

    print("=" * 60)
    print("LISTING DAY COLLECTOR TEST")
    print("=" * 60)

    # RELIANCE is already listed, so it is useful for testing
    # the instrument-resolution stage.
    result = collector.collect(
        symbol="RELIANCE",
        listing_date=date(2026, 8, 25),
        company_name="RELIANCE INDUSTRIES",
    )

    print("Status:", result["status"])
    print("Symbol:", result["symbol"])
    print("Listing date:", result["listing_date"])

    if result["instrument"]:
        print("Instrument:", result["instrument"])

    if result.get("collection"):
        print("Collection:", result["collection"])


if __name__ == "__main__":
    main()