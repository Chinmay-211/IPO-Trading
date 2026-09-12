import os
from datetime import date

import pytest

if os.getenv("RUN_LIVE_ANGEL_TESTS") != "1":
    pytest.skip(
        "Live Angel One tests require RUN_LIVE_ANGEL_TESTS=1.",
        allow_module_level=True,
    )

from backend.collectors.market.angel_one_instruments import (
    AngelOneInstrumentSource,
)
from backend.collectors.market.instrument_resolver import (
    InstrumentResolver,
)


def test_angel_one_instrument_resolver():

    source = AngelOneInstrumentSource()

    resolver = InstrumentResolver(
        source=source,
        provider="angel_one",
    )

    instrument = resolver.resolve(
        symbol="RELIANCE-EQ",
        company_name="RELIANCE INDUSTRIES",
        valid_from=date(2026, 8, 27),
    )

    print("\nResolved Angel One instrument:")
    print(instrument)

    assert instrument is not None
    assert instrument.symbol == "RELIANCE-EQ"
    assert instrument.exchange == "NSE"
    assert instrument.provider == "angel_one"
    assert instrument.provider_instrument_id == "2885"