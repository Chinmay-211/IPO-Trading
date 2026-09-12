from abc import ABC, abstractmethod
from datetime import datetime


class MarketDataSource(ABC):
    """Interface for historical and live market-data providers."""

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> list[dict]:
        """Return raw OHLCV candles for a symbol and time range."""
        raise NotImplementedError