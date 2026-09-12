from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class IPODiscovery:
    chittorgarh_ipo_id: int
    company_name: str
    ipo_type: Optional[str]
    ipo_open_date: Optional[str]
    ipo_close_date: Optional[str]
    listing_date: Optional[str]
    detail_url: str
    status: str = "DISCOVERED"
    discovered_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if self.chittorgarh_ipo_id <= 0:
            raise ValueError(
                "chittorgarh_ipo_id must be greater than zero"
            )

        if not self.company_name.strip():
            raise ValueError("company_name is required")

        if not self.detail_url.strip():
            raise ValueError("detail_url is required")

        if not self.discovered_at:
            self.discovered_at = datetime.now().isoformat()

        if not self.updated_at:
            self.updated_at = self.discovered_at

    def to_dict(self) -> dict:
        return {
            "chittorgarh_ipo_id": self.chittorgarh_ipo_id,
            "company_name": self.company_name,
            "ipo_type": self.ipo_type,
            "ipo_open_date": self.ipo_open_date,
            "ipo_close_date": self.ipo_close_date,
            "listing_date": self.listing_date,
            "detail_url": self.detail_url,
            "status": self.status,
            "discovered_at": self.discovered_at,
            "updated_at": self.updated_at,
        }