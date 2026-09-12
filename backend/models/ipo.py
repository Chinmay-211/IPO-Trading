from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class IPO:
    company_name: str
    symbol: Optional[str]
    listing_date: date
    issue_price: float
    issue_size: Optional[float]
    sector: Optional[str]
    source: str
    source_url: Optional[str]
    collected_at: datetime

    def to_dict(self) -> dict:
        return {
            "company_name": self.company_name,
            "symbol": self.symbol,
            "listing_date": self.listing_date.isoformat(),
            "issue_price": self.issue_price,
            "issue_size": self.issue_size,
            "sector": self.sector,
            "source": self.source,
            "source_url": self.source_url,
            "collected_at": self.collected_at.isoformat(),
        }