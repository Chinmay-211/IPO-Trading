from __future__ import annotations

from typing import Any


class IPORiskManager:
    """
    Portfolio-level risk management and circuit breakers for IPO trading.

    Enforces:
      1. Max daily loss limit (halts new entries once threshold is hit).
      2. Max concurrent open positions (prevents over-exposure across multiple IPOs).
      3. Max capital allocation per IPO trade.

    CRITICAL INVARIANT:
      Exits (Stop-Loss, Target, EOD force exit) are NEVER blocked.
    """

    def __init__(
        self,
        max_daily_loss: float | None = None,
        max_capital_per_ipo: float | None = None,
        max_concurrent_positions: int = 2,
    ):
        self.max_daily_loss = float(max_daily_loss) if max_daily_loss is not None else None
        self.max_capital_per_ipo = float(max_capital_per_ipo) if max_capital_per_ipo is not None else None
        self.max_concurrent_positions = max(1, int(max_concurrent_positions))

        self.trading_halted = False
        self.halt_reason: str | None = None

    def can_enter(
        self,
        symbol: str,
        price: float,
        quantity: int,
        current_realized_pnl: float = 0.0,
        active_positions: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """
        Evaluate if a new BUY entry is allowed under risk limits.

        Returns (allowed: bool, reason: str).
        """
        if self.trading_halted:
            return False, f"TRADING_HALTED: {self.halt_reason}"

        # 1. Daily loss circuit breaker check
        if self.max_daily_loss is not None and current_realized_pnl <= -self.max_daily_loss:
            self.trading_halted = True
            self.halt_reason = f"Daily loss limit of -{self.max_daily_loss} reached."
            return False, "DAILY_LOSS_LIMIT_REACHED"

        # 2. Concurrent positions check
        positions = active_positions or {}
        active_count = sum(
            1 for sym, pos in positions.items()
            if pos is not None and (
                pos.get("quantity", 0) > 0 if isinstance(pos, dict) else getattr(pos, "quantity", 0) > 0
            )
        )

        # If this is a new symbol entry and we already hit the max positions limit
        already_has_pos = symbol in positions and (
            positions[symbol].get("quantity", 0) > 0 if isinstance(positions[symbol], dict) else getattr(positions[symbol], "quantity", 0) > 0
        ) if symbol in positions and positions[symbol] else False

        if not already_has_pos and active_count >= self.max_concurrent_positions:
            return False, "MAX_POSITIONS_REACHED"

        # 3. Capital allocation limit per IPO
        required_capital = price * quantity
        if self.max_capital_per_ipo is not None and required_capital > self.max_capital_per_ipo:
            return False, "MAX_CAPITAL_EXCEEDED"

        return True, "APPROVED"

    def can_exit(self, symbol: str) -> tuple[bool, str]:
        """
        Exits (Target, SL, EOD) are ALWAYS allowed regardless of risk limits.
        """
        return True, "EXIT_APPROVED"

    def reset(self) -> None:
        """Reset daily halt state (for new trading day sessions)."""
        self.trading_halted = False
        self.halt_reason = None
