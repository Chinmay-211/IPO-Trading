from backend.services.historical_listing_data_batch import (
    HistoricalListingDataBatch,
)


class FakeCollector:

    def get_eligible_ipos(self):
        return [
            {
                "id": 1,
                "company_name": "TEST ONE",
                "symbol": "TESTONE",
                "listing_date": "2025-01-01",
            },
            {
                "id": 2,
                "company_name": "TEST TWO",
                "symbol": "TESTTWO",
                "listing_date": "2025-01-02",
            },
        ]

    def is_already_collected(self, symbol):
        return symbol == "TESTONE"


def test_historical_batch_dry_run():

    batch = HistoricalListingDataBatch(
        collector=FakeCollector()
    )

    result = batch.dry_run()

    assert result["total"] == 2
    assert result["ready"] == 1
    assert result["already_collected"] == 1