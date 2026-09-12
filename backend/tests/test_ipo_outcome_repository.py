from backend.storage.database import initialize_database
from backend.storage.ipo_outcome_repository import (
    IPOOutcomeRepository,
)


def main():
    initialize_database()

    repository = IPOOutcomeRepository()

    print("=" * 60)
    print("IPO OUTCOME REPOSITORY TEST")
    print("=" * 60)

    listing_gain = repository.calculate_listing_gain(
        listing_price=460.0,
        issue_price=425.0,
    )

    opening_gain = repository.calculate_opening_gain(
        opening_price=461.0,
        listing_price=460.0,
    )

    high_gain = repository.calculate_intraday_high_gain(
        high_price=508.65,
        opening_price=461.0,
    )

    low_drawdown = repository.calculate_intraday_low_drawdown(
        low_price=461.0,
        opening_price=461.0,
    )

    close_return = repository.calculate_close_return(
        closing_price=494.60,
        opening_price=461.0,
    )

    print("Listing gain:", listing_gain)
    print("Opening gain:", opening_gain)
    print("Intraday high gain:", high_gain)
    print("Intraday low drawdown:", low_drawdown)
    print("Close return:", close_return)

    assert round(listing_gain, 2) == 8.24
    assert round(opening_gain, 2) == 0.22
    assert round(high_gain, 2) == 10.34
    assert round(low_drawdown, 2) == 0.00
    assert round(close_return, 2) == 7.29

    print()
    print("ALL OUTCOME CALCULATIONS PASSED")


if __name__ == "__main__":
    main()