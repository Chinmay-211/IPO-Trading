from backend.collectors.ipo.investorgain_gmp_source import (
    InvestorGainGMPDataSource,
)


def main():
    source = InvestorGainGMPDataSource()

    requested_slug = "credent-connect-ipo"
    requested_id = 2252

    records = source.fetch(
        requested_slug,
        requested_id,
    )

    print("Requested slug:", requested_slug)
    print("Requested source ID:", requested_id)
    print("Records returned:", len(records))

    if records:
        print("Returned source URL:", records[0]["source_url"])
        print("Returned source ID:", records[0]["ipo_id"])

        for record in records:
            print(record)


if __name__ == "__main__":
    main()