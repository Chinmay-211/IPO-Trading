from backend.collectors.ipo.peer_valuation_source import (
    ChittorgarhPeerValuationSource,
)


def main():
    source = ChittorgarhPeerValuationSource()

    url = (
        "https://www.chittorgarh.com/"
        "ipo/tempsens-instruments-india-ipo/2668/"
    )

    result = source.fetch(url)

    print("Peer valuation:")
    print(result)


if __name__ == "__main__":
    main()