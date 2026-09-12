from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Candle:
    symbol: str
    timestamp: datetime

    open_price: float
    high_price: float
    low_price: float
    close_price: float

    volume: Optional[int]

    interval: str
    source: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "interval": self.interval,
            "source": self.source,
        }