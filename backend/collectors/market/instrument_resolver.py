from datetime import date

from backend.models.instrument import Instrument
from backend.storage.instrument_repository import InstrumentRepository


class InstrumentResolver:
    """Resolve exchange symbols to provider instrument mappings."""

    def __init__(
        self,
        source,
        provider: str,
        repository=None,
    ):
        self.source = source
        self.provider = provider
        self.repository = (
            repository
            or InstrumentRepository()
        )

    def resolve(
        self,
        symbol: str,
        company_name: str = "",
        valid_from: date | None = None,
    ) -> Instrument | None:
        """Resolve and store a provider instrument."""

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol is required")

        symbol = symbol.strip().upper()

        instrument = self.source.find_symbol(symbol)

        if instrument is None:
            return None

        # Provider-specific field normalization.
        if self.provider == "zerodha":
            if instrument.get("exchange") != "NSE":
                return None

            if instrument.get("segment") != "NSE":
                return None

            provider_instrument_id = instrument.get(
                "instrument_token"
            )

            resolved_symbol = instrument.get(
                "tradingsymbol",
                symbol,
            )

            instrument_name = instrument.get(
                "name",
                "",
            )

            isin = instrument.get("isin")

        elif self.provider == "angel_one":
            if instrument.get("exch_seg") != "NSE":
                return None

            provider_instrument_id = instrument.get(
                "token"
            )

            resolved_symbol = instrument.get(
                "symbol",
                symbol,
            )

            instrument_name = instrument.get(
                "name",
                "",
            )

            isin = None

        else:
            raise ValueError(
                f"Unsupported provider: {self.provider}"
            )

        if provider_instrument_id is None:
            raise ValueError(
                f"Instrument token missing for "
                f"{self.provider}:{symbol}"
            )

        resolved = Instrument(
            symbol=resolved_symbol,
            company_name=(
                company_name
                or instrument_name
                or symbol
            ),
            isin=isin,
            exchange="NSE",
            provider=self.provider,
            provider_instrument_id=str(
                provider_instrument_id
            ),
            valid_from=valid_from,
            valid_to=None,
        )

        self.repository.add(resolved)

        return resolved