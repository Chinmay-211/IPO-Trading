from datetime import datetime

from backend.models.candle import Candle
from backend.storage.candle_repository import CandleRepository


def main():
    candle = Candle(
        symbol="TESTCANDLE",
        timestamp=datetime(2026, 1, 2, 9, 15),
        open_price=100.0,
        high_price=105.0,
        low_price=99.0,
        close_price=103.0,
        volume=25000,
        interval="1m",
        source="test",
    )

    repository = CandleRepository()

    inserted = repository.add(candle)

    print("Inserted:", inserted)
    print("Candle count:", repository.count())
    print("Records:")

    for record in repository.get_for_symbol("TESTCANDLE"):
        print(record)


if __name__ == "__main__":
    main()