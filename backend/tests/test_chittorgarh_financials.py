from backend.collectors.ipo.chittorgarh_financials_source import (
    ChittorgarhFinancialsSource,
)


def main():
    source = ChittorgarhFinancialsSource()

    url = (
        "https://www.chittorgarh.com/ipo/"
        "tempsens-instruments-india-ipo/2668/"
    )

    result = source.fetch(url)

    print("Financial data:")
    print(result)


if __name__ == "__main__":
    main()