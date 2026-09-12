from backend.services.historical_listing_data_collector import (
    HistoricalListingDataCollector,
)


class HistoricalListingDataBatch:
    """Plan and execute historical IPO candle collection."""

    def __init__(self, collector=None):
        self.collector = (
            collector
            or HistoricalListingDataCollector()
        )

    def dry_run(self) -> dict:
        """Inspect eligible IPOs without calling market APIs."""

        ipos = self.collector.get_eligible_ipos()

        ready = []
        already_collected = []

        for ipo in ipos:
            if self.collector.is_already_collected(
                ipo["symbol"]
            ):
                already_collected.append(ipo)
            else:
                ready.append(ipo)

        return {
            "total": len(ipos),
            "ready": len(ready),
            "already_collected": len(
                already_collected
            ),
            "ready_ipos": ready,
            "already_collected_ipos": (
                already_collected
            ),
        }

    def run(
        self,
        skip_existing: bool = True,
    ) -> dict:
        """Execute historical IPO candle collection."""

        return self.collector.collect_all(
            skip_existing=skip_existing
        )