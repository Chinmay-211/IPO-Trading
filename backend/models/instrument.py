from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Instrument:
    symbol: str
    company_name: str
    isin: Optional[str]
    exchange: str

    provider: str
    provider_instrument_id: str

    valid_from: Optional[date]
    valid_to: Optional[date]

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "isin": self.isin,
            "exchange": self.exchange,
            "provider": self.provider,
            "provider_instrument_id": self.provider_instrument_id,
            "valid_from": (
                self.valid_from.isoformat()
                if self.valid_from
                else None
            ),
            "valid_to": (
                self.valid_to.isoformat()
                if self.valid_to
                else None
            ),
        }