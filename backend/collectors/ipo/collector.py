from datetime import datetime

from backend.models.ipo import IPO
from backend.storage.ipo_repository import IPORepository
from backend.validators.ipo_validator import validate_ipo


class IPOCollector:
    """Collect, validate, and store IPO records."""

    def __init__(self, source):
        self.source = source
        self.repository = IPORepository()

    def run(self) -> dict:
        raw_records = self.source.fetch()

        inserted = 0
        skipped = 0
        invalid = 0
        errors = []

        for raw_record in raw_records:
            try:
                normalized = self.source.normalize(raw_record)

                ipo = IPO(
                    company_name=normalized["company_name"],
                    symbol=normalized.get("symbol"),
                    listing_date=normalized["listing_date"],
                    issue_price=normalized["issue_price"],
                    issue_size=normalized.get("issue_size"),
                    sector=normalized.get("sector"),
                    source=normalized["source"],
                    source_url=normalized.get("source_url"),
                    collected_at=datetime.now(),
                )

                validation_errors = validate_ipo(ipo)

                if validation_errors:
                    invalid += 1
                    errors.append({
                        "company_name": normalized.get("company_name"),
                        "errors": validation_errors,
                    })
                    continue

                if self.repository.add(ipo):
                    inserted += 1
                else:
                    skipped += 1

            except Exception as exc:
                errors.append({
                    "record": raw_record,
                    "error": str(exc),
                })

        return {
            "fetched": len(raw_records),
            "inserted": inserted,
            "skipped": skipped,
            "invalid": invalid,
            "errors": errors,
        }