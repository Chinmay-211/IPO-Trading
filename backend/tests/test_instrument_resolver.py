from datetime import date

from backend.collectors.market.instrument_resolver import (
    InstrumentResolver,
)
from backend.collectors.market.zerodha_instruments import (
    ZerodhaInstrumentSource,
)
from backend.storage.instrument_repository import (
    InstrumentRepository,
)


def main():
    source = ZerodhaInstrumentSource()

    resolver = InstrumentResolver(
    source=source,
    provider="zerodha",
    )

    print("=" * 60)
    print("TEST 1: RELIANCE")
    print("=" * 60)

    reliance = resolver.resolve(
        symbol="RELIANCE",
        company_name="RELIANCE INDUSTRIES",
        valid_from=date.today(),
    )

    print("Resolved:", reliance)

    if reliance:
        print("Symbol:", reliance.symbol)
        print("Exchange:", reliance.exchange)
        print("Provider:", reliance.provider)
        print(
            "Instrument ID:",
            reliance.provider_instrument_id,
        )

    print()
    print("=" * 60)
    print("TEST 2: TEMPSENS")
    print("=" * 60)

    tempsens = resolver.resolve(
        symbol="TEMPSENS",
        company_name="Tempsens Instruments (India) Ltd.",
        valid_from=date(2026, 8, 28),
    )

    print("Resolved:", tempsens)

    print()
    print("=" * 60)
    print("STORED ZERODHA INSTRUMENTS")
    print("=" * 60)

    repository = InstrumentRepository()

    records = repository.get_by_symbol(
        "RELIANCE",
        "zerodha",
    )

    for record in records:
        print(record)


if __name__ == "__main__":
    main()