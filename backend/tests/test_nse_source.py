from backend.collectors.ipo.nse_source import NSEIPODataSource


def main():
    source = NSEIPODataSource()

    records = source.fetch()

    print("NSE connection successful")
    print("Records returned:", len(records))

    if records:
        print("First raw record:")
        print(records[0])

        print("\nFirst normalized record:")
        print(source.normalize(records[0]))


if __name__ == "__main__":
    main()