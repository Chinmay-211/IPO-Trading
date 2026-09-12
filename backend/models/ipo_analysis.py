from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class IPOAnalysis:
    ipo_id: int

    ipo_type: Optional[str] = None

    qib_subscription: Optional[float] = None
    overall_subscription: Optional[float] = None

    gmp_day_1: Optional[float] = None
    gmp_day_2: Optional[float] = None

    fresh_issue_percentage: Optional[float] = None
    ofs_percentage: Optional[float] = None

    anchor_investor_count: Optional[int] = None

    sales_year_1: Optional[float] = None
    sales_year_2: Optional[float] = None
    sales_year_3: Optional[float] = None

    profit_year_1: Optional[float] = None
    profit_year_2: Optional[float] = None
    profit_year_3: Optional[float] = None

    margin_year_1: Optional[float] = None
    margin_year_2: Optional[float] = None
    margin_year_3: Optional[float] = None

    debt_previous: Optional[float] = None
    debt_current: Optional[float] = None

    roe: Optional[float] = None
    roce: Optional[float] = None

    ipo_pe: Optional[float] = None
    peer_pe: Optional[float] = None

    source: Optional[str] = None
    source_url: Optional[str] = None

    collected_at: str = ""

    def __post_init__(self):
        if self.ipo_id <= 0:
            raise ValueError("ipo_id must be greater than zero")

        if not self.collected_at:
            self.collected_at = datetime.utcnow().isoformat()