from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


class MultiIPOLiveMonitor:
    """
    Manages multiple IPOs during live paper trading.

    Each IPO has isolated:
        - strategy/controller
        - execution service
        - latest candle
        - latest decision
        - latest execution result

    This class does NOT place real broker orders.
    """

    def __init__(
        self,
        on_result: Callable[
            [str, dict[str, Any]],
            Any,
        ] | None = None,
    ):
        self.on_result = on_result

        self._ipos: dict[
            str,
            dict[str, Any],
        ] = {}

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        if not isinstance(symbol, str):
            raise ValueError(
                "symbol must be a string."
            )

        symbol = symbol.strip().upper()

        if not symbol:
            raise ValueError(
                "symbol is required."
            )

        return symbol

    def register(
        self,
        symbol: str,
        controller: Any,
    ) -> None:
        """
        Register one IPO controller.
        """

        symbol = self._normalize_symbol(symbol)

        if controller is None:
            raise ValueError(
                "controller is required."
            )

        if symbol in self._ipos:
            raise ValueError(
                f"IPO already registered: {symbol}"
            )

        self._ipos[symbol] = {
            "symbol": symbol,
            "controller": controller,
            "last_candle": None,
            "last_decision": None,
            "last_execution": None,
            "running": True,
        }

    def unregister(
        self,
        symbol: str,
    ) -> None:
        symbol = self._normalize_symbol(symbol)

        self._ipos.pop(
            symbol,
            None,
        )

    def contains(
        self,
        symbol: str,
    ) -> bool:
        symbol = self._normalize_symbol(symbol)

        return symbol in self._ipos

    def symbols(self) -> list[str]:
        return list(self._ipos.keys())

    def count(self) -> int:
        return len(self._ipos)

    def start(
        self,
        symbol: str,
    ) -> None:
        symbol = self._normalize_symbol(symbol)

        if symbol not in self._ipos:
            raise KeyError(
                f"IPO is not registered: {symbol}"
            )

        self._ipos[symbol]["running"] = True

    def stop(
        self,
        symbol: str,
    ) -> None:
        symbol = self._normalize_symbol(symbol)

        if symbol not in self._ipos:
            raise KeyError(
                f"IPO is not registered: {symbol}"
            )

        self._ipos[symbol]["running"] = False

    def is_running(
        self,
        symbol: str,
    ) -> bool:
        symbol = self._normalize_symbol(symbol)

        if symbol not in self._ipos:
            return False

        return bool(
            self._ipos[symbol]["running"]
        )

    def process_candle(
        self,
        symbol: str,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Send one completed candle to the correct IPO controller.

        The controller is expected to expose one of:

            process_candle(candle)
            on_candle(candle)
            process(candle)

        The returned value is treated as the strategy/
        execution result.
        """

        symbol = self._normalize_symbol(symbol)

        if symbol not in self._ipos:
            raise KeyError(
                f"IPO is not registered: {symbol}"
            )

        if not isinstance(candle, dict):
            raise ValueError(
                "candle must be a dictionary."
            )

        state = self._ipos[symbol]

        if not state["running"]:
            return None

        state["last_candle"] = dict(candle)

        controller = state["controller"]

        result = None

        process_candle = getattr(
            controller,
            "process_candle",
            None,
        )

        if callable(process_candle):
            result = process_candle(candle)

        else:
            on_candle = getattr(
                controller,
                "on_candle",
                None,
            )

            if callable(on_candle):
                result = on_candle(candle)

            else:
                process = getattr(
                    controller,
                    "process",
                    None,
                )

                if callable(process):
                    result = process(candle)

                else:
                    raise TypeError(
                        "Controller must expose "
                        "process_candle(), on_candle(), "
                        "or process()."
                    )

        if isinstance(result, dict):
            state["last_decision"] = result
            state["last_execution"] = result

        if self.on_result is not None:
            self.on_result(
                symbol,
                result,
            )

        return result

    def get_state(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """
        Return state for one IPO or all IPOs.
        """

        if symbol is not None:
            symbol = self._normalize_symbol(symbol)

            if symbol not in self._ipos:
                raise KeyError(
                    f"IPO is not registered: {symbol}"
                )

            state = self._ipos[symbol]

            return {
                "symbol": state["symbol"],
                "running": state["running"],
                "last_candle": state["last_candle"],
                "last_decision": state["last_decision"],
                "last_execution": state["last_execution"],
            }

        return {
            symbol: {
                "symbol": state["symbol"],
                "running": state["running"],
                "last_candle": state["last_candle"],
                "last_decision": state["last_decision"],
                "last_execution": state["last_execution"],
            }
            for symbol, state in self._ipos.items()
        }

    def reset(
        self,
        symbol: str | None = None,
    ) -> None:
        """
        Reset one IPO or all IPO state.
        """

        if symbol is not None:
            symbol = self._normalize_symbol(symbol)

            if symbol not in self._ipos:
                raise KeyError(
                    f"IPO is not registered: {symbol}"
                )

            state = self._ipos[symbol]

            state["last_candle"] = None
            state["last_decision"] = None
            state["last_execution"] = None

            return

        for state in self._ipos.values():
            state["last_candle"] = None
            state["last_decision"] = None
            state["last_execution"] = None

    def clear(self) -> None:
        """
        Remove all registered IPOs.
        """

        self._ipos.clear()