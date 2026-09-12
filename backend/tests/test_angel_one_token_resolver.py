from backend.collectors.market.angel_one_token_resolver import (
    AngelOneTokenResolver,
)


class FakeInstrumentSource:
    def __init__(self):
        self._instruments = [
            {
                "token": "758670",
                "symbol": "ARCIIL-SM",
                "name": "ARCIIL",
                "exch_seg": "NSE",
                "instrumenttype": "",
            },
            {
                "token": "765356",
                "symbol": "HORIZONIND-EQ",
                "name": "HORIZONIND",
                "exch_seg": "NSE",
                "instrumenttype": "",
            },
            {
                "token": "765361",
                "symbol": "LALITHAA-EQ",
                "name": "LALITHAA",
                "exch_seg": "NSE",
                "instrumenttype": "",
            },
            {
                "token": "99926000",
                "symbol": "NIFTY",
                "name": "NIFTY",
                "exch_seg": "NSE",
                "instrumenttype": "AMXIDX",
            },
        ]

        self.load_count = 0

    def _load_instruments(self):
        self.load_count += 1


def test_resolve_token_to_symbol():
    source = FakeInstrumentSource()

    resolver = AngelOneTokenResolver(
        instrument_source=source
    )

    assert resolver.resolve("758670") == "ARCIIL-SM"
    assert resolver.resolve(765356) == "HORIZONIND-EQ"
    assert resolver.resolve("765361") == "LALITHAA-EQ"


def test_find_returns_instrument():
    source = FakeInstrumentSource()

    resolver = AngelOneTokenResolver(
        instrument_source=source
    )

    instrument = resolver.find("758670")

    assert instrument is not None
    assert instrument["symbol"] == "ARCIIL-SM"
    assert instrument["name"] == "ARCIIL"


def test_find_token():
    source = FakeInstrumentSource()

    resolver = AngelOneTokenResolver(
        instrument_source=source
    )

    instrument = resolver.find_token(
        "HORIZONIND-EQ"
    )

    assert instrument is not None
    assert instrument["token"] == "765356"


def test_unknown_token_returns_none():
    source = FakeInstrumentSource()

    resolver = AngelOneTokenResolver(
        instrument_source=source
    )

    assert resolver.resolve("DOES_NOT_EXIST") is None


def test_instrument_master_is_loaded_once():
    source = FakeInstrumentSource()

    resolver = AngelOneTokenResolver(
        instrument_source=source
    )

    resolver.resolve("758670")
    resolver.resolve("765356")
    resolver.resolve("765361")

    assert source.load_count == 1