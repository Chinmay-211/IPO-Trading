from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from backend.services.live_ipo_paper_engine import LiveIPOPaperEngine


class AngelOneLiveEngineFeeder:
    """
    Connects Angel One WebSocket tick events to LiveIPOPaperEngine.

    Maps Angel One instrument tokens to trading symbols and feeds
    validated ticks into the engine's processing pipeline.
    """

    def __init__(
        self,
        engine: LiveIPOPaperEngine,
        token_to_symbol: dict[str, str],
        ws_source: Any | None = None,
    ):
        if not isinstance(engine, LiveIPOPaperEngine):
            raise TypeError("engine must be an instance of LiveIPOPaperEngine.")

        if not isinstance(token_to_symbol, dict):
            raise TypeError("token_to_symbol must be a dictionary.")

        # Normalize token -> uppercase symbol
        self.token_to_symbol: dict[str, str] = {
            str(tok).strip(): sym.strip().upper()
            for tok, sym in token_to_symbol.items()
            if str(tok).strip() and str(sym).strip()
        }

        self.engine = engine
        self.ws_source = ws_source

        self.ticks_received = 0
        self.ticks_forwarded = 0
        self.ticks_dropped = 0
        self.last_error: str | None = None

    def on_tick(self, tick_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle a normalized tick from AngelOneWebSocketSource.

        Maps token to symbol and feeds the tick to the engine.
        Returns the engine's decision/result if any.
        """
        self.ticks_received += 1

        if not isinstance(tick_data, dict):
            self.ticks_dropped += 1
            return None

        token = str(tick_data.get("token", "")).strip()
        symbol = self.token_to_symbol.get(token)

        # If token not in map, check if symbol was already provided in tick_data
        if not symbol:
            raw_sym = tick_data.get("symbol")
            if raw_sym and isinstance(raw_sym, str):
                normalized_sym = raw_sym.strip().upper()
                if normalized_sym in self.engine.pipelines:
                    symbol = normalized_sym

        if not symbol or symbol not in self.engine.pipelines:
            self.ticks_dropped += 1
            return None

        timestamp = tick_data.get("timestamp")
        if not isinstance(timestamp, datetime):
            self.ticks_dropped += 1
            return None

        price = tick_data.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            self.ticks_dropped += 1
            return None

        volume = tick_data.get("volume", 0)
        if not isinstance(volume, int) or volume < 0:
            volume = 0

        engine_tick = {
            "symbol": symbol,
            "timestamp": timestamp,
            "price": float(price),
            "volume": volume,
        }

        try:
            result = self.engine.process_tick(engine_tick)
            self.ticks_forwarded += 1
            return result
        except Exception as e:
            self.last_error = str(e)
            self.ticks_dropped += 1
            return None

    def start(self) -> None:
        """Start the engine and optionally connect the underlying WebSocket."""
        self.engine.start()
        if self.ws_source is not None:
            connect = getattr(self.ws_source, "connect", None)
            if callable(connect):
                connect()

    def stop(self) -> None:
        """Stop the engine and close the underlying WebSocket if active."""
        self.engine.stop()
        if self.ws_source is not None:
            close = getattr(self.ws_source, "close", None)
            if callable(close):
                close()

    def get_stats(self) -> dict[str, Any]:
        """Return feeder throughput stats."""
        return {
            "ticks_received": self.ticks_received,
            "ticks_forwarded": self.ticks_forwarded,
            "ticks_dropped": self.ticks_dropped,
            "mapped_tokens": len(self.token_to_symbol),
            "last_error": self.last_error,
        }
