from datetime import date

from backend.models.instrument import Instrument
from backend.storage.instrument_repository import InstrumentRepository


def main():
    instrument = Instrument(
        symbol="TESTINST",
        company_name="TEST INSTRUMENT",
        isin="INE000TEST000",
        exchange="NSE",
        provider="test",
        provider_instrument_id="TEST123",
        valid_from=date(2026, 1, 2),
        valid_to=None,
    )

    repository = InstrumentRepository()

    inserted = repository.add(instrument)

    print("Inserted:", inserted)
    print("Instrument count:", repository.count())
    print("Records:")

    for record in repository.get_by_symbol(
        "TESTINST",
        "test",
    ):
        print(record)


if __name__ == "__main__":
    main()