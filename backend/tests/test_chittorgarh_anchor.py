from backend.collectors.ipo.chittorgarh_anchor_source import (
    ChittorgarhAnchorSource,
)


def main():
    source = ChittorgarhAnchorSource()

    url = (
        "https://www.chittorgarh.com/ipo_subscription/"
        "tempsens-instruments-india-ipo/2668/"
    )

    result = source.fetch(url)

    print("Anchor data:")
    print(result)


if __name__ == "__main__":
    main()