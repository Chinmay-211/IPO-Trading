from datetime import date, datetime

from backend.models.ipo import IPO
from backend.storage.ipo_repository import IPORepository
from backend.storage.subscription_repository import SubscriptionRepository


def main():
    ipo_repository = IPORepository()

    ipo = IPO(
        company_name="Tempsens Instruments (India) Limited",
        symbol=None,
        listing_date=date(2026, 8, 25),
        issue_price=425.0,
        issue_size=None,
        sector=None,
        source="Chittorgarh",
        source_url=(
            "https://www.chittorgarh.com/ipo/"
            "tempsens-instruments-india-ipo/2668/"
        ),
        collected_at=datetime.now(),
    )

    inserted = ipo_repository.add(ipo)

    print("IPO inserted:", inserted)

    stored_ipo = ipo_repository.get_by_company_and_date(
        ipo.company_name,
        ipo.listing_date,
    )

    print("Stored IPO:", stored_ipo)

    if stored_ipo is None:
        raise RuntimeError("IPO was not found after insertion.")

    subscription_repository = SubscriptionRepository()

    snapshot = {
        "ipo_id": stored_ipo["id"],
        "subscription_date": "2026-08-21",
        "subscription_day": 2,
        "qib_subscription": 3.31,
        "nii_subscription": 52.98,
        "retail_subscription": 18.73,
        "overall_subscription": 21.69,
        "total_applications": 2225599,
        "source": "Chittorgarh",
        "source_url": (
            "https://www.chittorgarh.net/documents/"
            "subscription/2668/details.html"
        ),
        "collected_at": datetime.now().isoformat(),
    }

    snapshot_inserted = subscription_repository.add(snapshot)

    print("Subscription snapshot inserted:", snapshot_inserted)


if __name__ == "__main__":
    main()