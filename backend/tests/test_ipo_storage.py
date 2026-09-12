from datetime import date, datetime

from backend.models.ipo import IPO
from backend.storage.ipo_repository import IPORepository


def main():
    ipo = IPO(
        company_name="TEST IPO",
        symbol="TESTIPO",
        listing_date=date(2026, 1, 1),
        issue_price=100.0,
        issue_size=500.0,
        sector="Technology",
        source="test",
        source_url="https://example.com",
        collected_at=datetime.now(),
    )

    repository = IPORepository()

    inserted = repository.add(ipo)

    print("Inserted:", inserted)
    print("IPO count:", repository.count())
    print("Records:")

    for record in repository.get_all():
        print(record)


if __name__ == "__main__":
    main()
