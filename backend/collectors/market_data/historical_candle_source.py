from abc import ABC, abstractmethod


class HistoricalCandleSource(ABC):
    """Interface for historical intraday market-data providers."""

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "1m",
    ) -> list[dict]:
        """
        Return historical candles in chronological order.

        Each candle must contain:

        timestamp
        open_price
        high_price
        low_price
        close_price
        volume
        """
        raise NotImplementedError