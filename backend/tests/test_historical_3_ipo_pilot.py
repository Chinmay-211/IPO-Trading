import os
import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

from backend.services.historical_listing_data_collector import (
    HistoricalListingDataCollector,
)


def test_three_ipo_historical_pilot():

    collector = HistoricalListingDataCollector()

    ipos = [
        {
            "id": 200,
            "company_name": "Fascinate Textiles Limited",
            "symbol": "FASCINATE",
            "listing_date": "2026-08-24",
        },
        {
            "id": 201,
            "company_name": "Horizon Industrial Parks Limited",
            "symbol": "HORIZONIND",
            "listing_date": "2026-08-24",
        },
        {
            "id": 202,
            "company_name": "Lalithaa Jewellery Mart Limited",
            "symbol": "LALITHAA",
            "listing_date": "2026-08-24",
        },
    ]

    for ipo in ipos:

        print(
            f"\nCollecting "
            f"{ipo['symbol']} "
            f"({ipo['listing_date']})"
        )

        result = collector.collect_one(
            ipo,
            skip_existing=True,
        )

        print(result)

        assert result["status"] in {
            "COLLECTED",
            "ALREADY_COLLECTED",
            "NOT_AVAILABLE",
        }