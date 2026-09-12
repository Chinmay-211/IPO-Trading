from backend.collectors.ipo.investorgain_gmp_source import (
    InvestorGainGMPDataSource,
)
from backend.storage.gmp_repository import GMPRepository


def main():
    source = InvestorGainGMPDataSource()

    records = source.fetch(
        "credent-connect-ipo",
        2252,
    )

    print("Collected:", len(records))

    repository = GMPRepository()

    inserted = 0
    skipped = 0

    for record in records:
        if repository.add(record):
            inserted += 1
        else:
            skipped += 1

    print("Inserted:", inserted)
    print("Skipped:", skipped)

    stored = repository.get_by_ipo(2252)

    print("Stored records:", len(stored))

    for record in stored:
        print(record)


if __name__ == "__main__":
    main()