from backend.services.ipo_historical_data_collector import (
    IPOHistoricalDataCollector,
)


class FakeCandleSource:
    def fetch(self, symbol, listing_date, interval):
        return [
            {
                "timestamp": "2026-08-24T10:00:00+05:30",
                "open_price": 60.18,
                "high_price": 60.25,
                "low_price": 59.10,
                "close_price": 59.45,
                "volume": 9071980,
            },
            {
                "timestamp": "2026-08-24T10:01:00+05:30",
                "open_price": 59.41,
                "high_price": 59.60,
                "low_price": 59.00,
                "close_price": 59.31,
                "volume": 2580170,
            },
        ]


class FakeCandleRepository:
    def __init__(self):
        self.saved = []

    def save_candle(self, **kwargs):
        self.saved.append(kwargs)
        return True


class FakeInstrumentResolver:
    def find(self, symbol, exchange):
        return {
            "token": "765356",
            "symbol": "HORIZONIND-EQ",
            "name": "HORIZONIND",
            "exch_seg": "NSE",
        }


def test_ipo_historical_data_collector():
    repository = FakeCandleRepository()

    collector = IPOHistoricalDataCollector(
        candle_source=FakeCandleSource(),
        candle_repository=repository,
        instrument_resolver=FakeInstrumentResolver(),
    )

    ipo = {
        "id": 123,
        "company_name": "Horizon Industrial Parks Limited",
        "symbol": "HORIZONIND",
        "listing_date": "2026-08-24",
    }

    result = collector.collect_one(ipo)

    assert result["status"] == "COLLECTED"
    assert result["ipo_id"] == 123
    assert result["provider_instrument_id"] == "765356"
    assert result["collection"]["fetched"] == 2
    assert result["collection"]["inserted"] == 2

    assert len(repository.saved) == 2

    assert repository.saved[0]["ipo_id"] == 123
    assert repository.saved[0]["provider_instrument_id"] == "765356"
    assert repository.saved[0]["symbol"] == "765356"