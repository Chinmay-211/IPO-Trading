from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class ListingDayData:
    symbol: str
    listing_date: date

    listing_price: Optional[float]
    opening_price: Optional[float]
    high_price: Optional[float]
    low_price: Optional[float]
    closing_price: Optional[float]

    volume: Optional[int]

    source: str
    source_url: Optional[str]
    collected_at: datetime

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "listing_date": self.listing_date.isoformat(),
            "listing_price": self.listing_price,
            "opening_price": self.opening_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "closing_price": self.closing_price,
            "volume": self.volume,
            "source": self.source,
            "source_url": self.source_url,
            "collected_at": self.collected_at.isoformat(),
        }