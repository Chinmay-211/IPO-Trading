from datetime import datetime

from backend.collectors.market.zerodha_instruments import (
    ZerodhaInstrumentSource,
)
from backend.collectors.market.zerodha_source import (
    ZerodhaDataSource,
)


def main():
    symbol = "RELIANCE"

    instrument_source = ZerodhaInstrumentSource()

    instrument = instrument_source.find_symbol(symbol)

    if instrument is None:
        raise RuntimeError(
            f"Instrument not found: {symbol}"
        )

    instrument_token = instrument["instrument_token"]

    print("Symbol:", symbol)
    print("Instrument token:", instrument_token)

    data_source = ZerodhaDataSource()

    candles = data_source.get_candles(
        symbol=str(instrument_token),
        start=datetime(2026, 8, 20, 9, 15),
        end=datetime(2026, 8, 20, 15, 30),
        interval="minute",
    )

    print("Candles returned:", len(candles))

    if candles:
        print("First candle:")
        print(candles[0])

        print("Last candle:")
        print(candles[-1])


if __name__ == "__main__":
    main()