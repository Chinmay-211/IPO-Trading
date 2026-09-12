from datetime import date, datetime

from backend.models.ipo import IPO
from backend.validators.ipo_validator import validate_ipo


def main():
    valid_ipo = IPO(
        company_name="Valid IPO",
        symbol="VALID",
        listing_date=date(2025, 1, 1),
        issue_price=100.0,
        issue_size=500.0,
        sector="Technology",
        source="test",
        source_url=None,
        collected_at=datetime.now(),
    )

    invalid_ipo = IPO(
        company_name="",
        symbol=None,
        listing_date=date(2030, 1, 1),
        issue_price=-10.0,
        issue_size=-100.0,
        sector=None,
        source="",
        source_url=None,
        collected_at=datetime.now(),
    )

    print("Valid IPO errors:", validate_ipo(valid_ipo))
    print("Invalid IPO errors:", validate_ipo(invalid_ipo))


if __name__ == "__main__":
    main()