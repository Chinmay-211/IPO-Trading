from datetime import date

from backend.collectors.listing.listing_day_collector import (
    ListingDayCollector,
)
from backend.collectors.market.angel_one_instruments import (
    AngelOneInstrumentSource,
)
from backend.collectors.market.angel_one_source import (
    AngelOneDataSource,
)
from backend.collectors.market.collector import (
    MarketDataCollector,
)
from backend.collectors.market.instrument_resolver import (
    InstrumentResolver,
)
from backend.storage.candle_repository import (
    CandleRepository,
)
from backend.storage.ipo_repository import (
    IPORepository,
)


class HistoricalListingDataCollector:
    """
    High-level service for collecting historical IPO
    listing-day candles.
    """

    def __init__(
        self,
        ipo_repository=None,
        candle_repository=None,
        listing_day_collector=None,
    ):
        self.ipo_repository = (
            ipo_repository
            or IPORepository()
        )

        self.candle_repository = (
            candle_repository
            or CandleRepository()
        )

        self.listing_day_collector = (
            listing_day_collector
            or ListingDayCollector(
                instrument_resolver=InstrumentResolver(
                    source=AngelOneInstrumentSource(),
                    provider="angel_one",
                ),
                market_collector=MarketDataCollector(
                    AngelOneDataSource()
                ),
            )
        )

    def get_eligible_ipos(self) -> list[dict]:
        today = date.today().isoformat()

        rows = self.ipo_repository.get_all()

        return [
            row
            for row in rows
            if (
                row.get("listing_date")
                and row["listing_date"] < today
                and row.get("symbol")
                and str(row.get("source", "")).lower()
                != "mock"
            )
        ]

    def is_already_collected(
        self,
        ipo: dict,
    ) -> bool:
        ipo_id = ipo["id"]

        from backend.storage.database import get_connection

        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM candles
                WHERE ipo_id = ?
                """,
                (ipo_id,),
            ).fetchone()

            return row["count"] > 0

        finally:
            connection.close()

    def collect_one(
        self,
        ipo: dict,
        skip_existing: bool = True,
    ) -> dict:
        if (
            skip_existing
            and self.is_already_collected(ipo)
        ):
            return {
                "status": "ALREADY_COLLECTED",
                "ipo_id": ipo["id"],
                "symbol": ipo["symbol"],
                "listing_date": ipo["listing_date"],
                "reason": (
                    "Candles already exist for "
                    "this IPO."
                ),
            }

        listing_date = date.fromisoformat(
            ipo["listing_date"]
        )

        result = self.listing_day_collector.collect(
            symbol=ipo["symbol"],
            listing_date=listing_date,
            company_name=ipo["company_name"],
        )

        return {
            "status": result["status"],
            "ipo_id": ipo["id"],
            "company_name": ipo["company_name"],
            "symbol": result.get(
                "symbol",
                ipo["symbol"],
            ),
            "listing_date": ipo["listing_date"],
            "instrument": result.get("instrument"),
            "collection": result.get("collection"),
            "reason": result.get("reason"),
        }

    def collect_all(
        self,
        skip_existing: bool = True,
    ) -> dict:
        ipos = self.get_eligible_ipos()

        results = []

        collected = 0
        already_collected = 0
        not_available = 0
        failed = 0

        for index, ipo in enumerate(ipos, start=1):

            print(
                f"[{index}/{len(ipos)}] "
                f"{ipo['symbol']} "
                f"({ipo['listing_date']})"
            )

            try:
                result = self.collect_one(
                    ipo,
                    skip_existing=skip_existing,
                )

                results.append({
                    "ipo_id": ipo["id"],
                    "company_name": ipo["company_name"],
                    "symbol": ipo["symbol"],
                    "listing_date": ipo["listing_date"],
                    "result": result,
                })

                status = result["status"]

                if status == "COLLECTED":
                    collected += 1

                elif status == "ALREADY_COLLECTED":
                    already_collected += 1

                elif status == "NOT_AVAILABLE":
                    not_available += 1

            except Exception as exc:

                failed += 1

                results.append({
                    "ipo_id": ipo["id"],
                    "company_name": ipo["company_name"],
                    "symbol": ipo["symbol"],
                    "listing_date": ipo["listing_date"],
                    "result": {
                        "status": "FAILED",
                        "error": str(exc),
                    },
                })

                print(
                    f"  FAILED: {exc}"
                )

        return {
            "total": len(ipos),
            "collected": collected,
            "already_collected": already_collected,
            "not_available": not_available,
            "failed": failed,
            "results": results,
        }