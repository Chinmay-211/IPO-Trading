import os
import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

from backend.collectors.market.angel_one_instruments import (
    AngelOneInstrumentSource,
)


def test_angel_one_instrument_source():
    source = AngelOneInstrumentSource()

    instrument = source.find_symbol(
        "RELIANCE-EQ"
    )

    print("\nAngel One instrument:")
    print(instrument)

    assert instrument is not None
    assert instrument["symbol"] == "RELIANCE-EQ"
    assert instrument["exch_seg"] == "NSE"
    assert instrument["token"] == "2885"


if __name__ == "__main__":
    test_angel_one_instrument_source()