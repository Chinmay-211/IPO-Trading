from backend.collectors.ipo.chittorgarh_subscription_source import (
    ChittorgarhSubscriptionDataSource,
)


def main():
    source = ChittorgarhSubscriptionDataSource()

    data = source.fetch(
    2668,
    detail_url=(
        "https://www.chittorgarh.com/ipo/"
        "tempsens-instruments-india-ipo/2668/"
    ),
)

    print("Subscription data:")
    print(data)


if __name__ == "__main__":
    main()