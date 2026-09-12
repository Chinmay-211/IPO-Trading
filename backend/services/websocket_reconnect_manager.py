from __future__ import annotations

import time
from typing import Any, Callable


class WebSocketReconnectManager:
    """
    Manages WebSocket reconnection health with exponential backoff.

    Calculates backoff delays: 1s, 2s, 4s, 8s, 16s, up to max_delay (30s).
    Automatically re-subscribes registered tokens upon successful reconnection.
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        max_retries: int = 10,
    ):
        self.base_delay = max(0.1, float(base_delay))
        self.max_delay = max(self.base_delay, float(max_delay))
        self.backoff_factor = max(1.1, float(backoff_factor))
        self.max_retries = max(1, int(max_retries))

        self.retry_count = 0
        self.total_reconnects = 0
        self.is_reconnecting = False
        self.last_error: str | None = None

    def get_backoff_delay(self, attempt: int | None = None) -> float:
        """Calculate the backoff delay for the given attempt count (0-indexed)."""
        idx = self.retry_count if attempt is None else attempt
        delay = self.base_delay * (self.backoff_factor ** idx)
        return min(delay, self.max_delay)

    def on_connected(self) -> None:
        """Reset retry counters upon successful connection."""
        self.retry_count = 0
        self.is_reconnecting = False
        self.last_error = None

    def attempt_reconnect(
        self,
        connect_fn: Callable[[], Any],
        subscribe_fn: Callable[[list[str]], Any] | None = None,
        tokens: list[str] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> bool:
        """
        Attempt a single reconnection with backoff.

        Invokes sleep_fn(delay), runs connect_fn(), and if successful,
        re-subscribes tokens using subscribe_fn.
        """
        if self.retry_count >= self.max_retries:
            raise RuntimeError(
                f"Maximum reconnection attempts ({self.max_retries}) exceeded."
            )

        delay = self.get_backoff_delay()
        self.is_reconnecting = True
        sleep_fn(delay)

        try:
            connect_fn()
            self.total_reconnects += 1
            self.on_connected()

            if subscribe_fn is not None and tokens:
                subscribe_fn(tokens)

            return True
        except Exception as e:
            self.retry_count += 1
            self.last_error = str(e)
            return False

    def get_stats(self) -> dict[str, Any]:
        """Return reconnection statistics."""
        return {
            "retry_count": self.retry_count,
            "total_reconnects": self.total_reconnects,
            "is_reconnecting": self.is_reconnecting,
            "max_retries": self.max_retries,
            "next_delay_seconds": self.get_backoff_delay(),
            "last_error": self.last_error,
        }
