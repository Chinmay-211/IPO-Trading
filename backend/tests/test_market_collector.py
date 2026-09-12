from datetime import datetime

from backend.collectors.market.base import MarketDataSource
from backend.collectors.market.collector import MarketDataCollector


class MockMarketDataSource(MarketDataSource):

    def get_candles(self, symbol, start, end, interval="1m"):
        return [
            {
                "timestamp": datetime(2026, 1, 2, 9, 15),
                "open": 100,
                "high": 105,
                "low": 99,
                "close": 103,
                "volume": 25000,
                "source": "mock",
            }
        ]


def main():
    collector = MarketDataCollector(
        MockMarketDataSource()
    )

    result = collector.collect(
        symbol="MOCKMARKET",
        start=datetime(2026, 1, 2, 9, 15),
        end=datetime(2026, 1, 2, 9, 16),
    )

    print(result)


if __name__ == "__main__":
    main()