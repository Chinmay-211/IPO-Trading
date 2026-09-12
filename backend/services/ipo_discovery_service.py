from backend.collectors.ipo.chittorgarh_source import (
    ChittorgarhIPODataSource,
)
from backend.models.ipo_discovery import IPODiscovery
from backend.storage.ipo_discovery_repository import (
    IPODiscoveryRepository,
)


class IPODiscoveryService:
    """Discover and persist IPOs from Chittorgarh."""

    def __init__(
        self,
        source=None,
        repository=None,
    ):
        self.source = (
            source or ChittorgarhIPODataSource()
        )

        self.repository = (
            repository or IPODiscoveryRepository()
        )

    def run(self) -> dict:
        records = self.source.fetch()

        inserted = 0
        skipped = 0
        errors = []

        for record in records:
            try:
                discovery = IPODiscovery(
                    chittorgarh_ipo_id=record["ipo_id"],
                    company_name=record["company_name"],
                    ipo_type=record.get("ipo_type"),
                    ipo_open_date=record.get(
                        "ipo_open_date"
                    ),
                    ipo_close_date=record.get(
                        "ipo_close_date"
                    ),
                    listing_date=record.get(
                        "listing_date"
                    ),
                    detail_url=record["detail_url"],
                )

                if self.repository.add(discovery):
                    inserted += 1
                else:
                    skipped += 1

            except Exception as exc:
                errors.append({
                    "record": record,
                    "error": str(exc),
                })

        return {
            "fetched": len(records),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }