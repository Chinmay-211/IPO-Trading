from __future__ import annotations

from typing import Any

from backend.collectors.market.angel_one_instruments import (
    AngelOneInstrumentSource,
)


class AngelOneTokenResolver:
    """
    Resolve Angel One instrument tokens into trading symbols.

    Example:

        758670
            ↓
        ARCIIL-SM

    This keeps broker-specific instrument identifiers
    out of the strategy and paper-trading layers.
    """

    def __init__(
        self,
        instrument_source: AngelOneInstrumentSource | None = None,
    ):
        self.source = (
            instrument_source
            or AngelOneInstrumentSource()
        )

        self._token_to_symbol: dict[str, str] = {}
        self._symbol_to_instrument: dict[
            str,
            dict[str, Any],
        ] = {}

        self._loaded = False

    def _load(self) -> None:
        """
        Load the Angel One instrument master once.
        """

        if self._loaded:
            return

        self.source._load_instruments()

        for instrument in self.source._instruments:
            if instrument.get("exch_seg") != "NSE":
                continue

            token = instrument.get("token")
            symbol = instrument.get("symbol")

            if not token or not symbol:
                continue

            token = str(token).strip()
            symbol = str(symbol).strip().upper()

            self._token_to_symbol[token] = symbol
            self._symbol_to_instrument[symbol] = instrument

        self._loaded = True

    def resolve(
        self,
        token: str | int,
    ) -> str | None:
        """
        Resolve an Angel One token to its trading symbol.
        """

        self._load()

        normalized = str(token).strip()

        if not normalized:
            return None

        return self._token_to_symbol.get(
            normalized
        )

    def find(
        self,
        token: str | int,
    ) -> dict[str, Any] | None:
        """
        Resolve a token and return the complete instrument.
        """

        self._load()

        symbol = self.resolve(token)

        if symbol is None:
            return None

        return self._symbol_to_instrument.get(
            symbol
        )

    def find_token(
        self,
        symbol: str,
    ) -> dict[str, Any] | None:
        """
        Resolve a trading symbol to its Angel One instrument.
        """

        self._load()

        normalized = symbol.strip().upper()

        return self._symbol_to_instrument.get(
            normalized
        )

    def clear(self) -> None:
        """
        Clear the local resolver cache.
        """

        self._token_to_symbol.clear()
        self._symbol_to_instrument.clear()
        self._loaded = False