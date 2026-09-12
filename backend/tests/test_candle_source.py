from backend.collectors.market_data.historical_candle_source import (
    HistoricalCandleSource,
)


class TestHistoricalCandleSource(
    HistoricalCandleSource
):
    def fetch(
        self,
        symbol: str,
        listing_date: str,
        interval: str = "1m",
    ) -> list[dict]:

        return [
            {
                "timestamp": (
                    f"{listing_date} 09:15:00"
                ),
                "open_price": 100.0,
                "high_price": 101.0,
                "low_price": 99.0,
                "close_price": 100.5,
                "volume": 1000,
            },
            {
                "timestamp": (
                    f"{listing_date} 09:16:00"
                ),
                "open_price": 100.5,
                "high_price": 102.0,
                "low_price": 100.0,
                "close_price": 101.5,
                "volume": 1200,
            },
        ]