from __future__ import annotations

import os


class LiveTradingSafetyViolation(Exception):
    """Raised when an attempt to execute live real-money trades is made without explicit safety clearance."""
    pass


class LiveBrokerGuard:
    """
    Production dual-confirmation safety lock.

    CRITICAL SAFETY RULES:
      1. Default mode is strictly PAPER.
      2. Live real-money trading is BLOCKED by default.
      3. Live trading ONLY unlocks if:
           - os.environ.get("TRADING_MODE") == "LIVE"
           - os.environ.get("LIVE_TRADING_CONFIRMATION") == "I_UNDERSTAND_REAL_MONEY_RISK"
    """

    SAFETY_CONFIRMATION_STRING = "I_UNDERSTAND_REAL_MONEY_RISK"

    @classmethod
    def is_live_trading_enabled(cls) -> bool:
        mode = os.environ.get("TRADING_MODE", "").strip().upper()
        confirmation = os.environ.get("LIVE_TRADING_CONFIRMATION", "").strip()
        return mode == "LIVE" and confirmation == cls.SAFETY_CONFIRMATION_STRING

    @classmethod
    def enforce_live_trading_safety(cls) -> None:
        """
        Verify that live real-money trading has been explicitly confirmed.
        Raises LiveTradingSafetyViolation if conditions are not strictly satisfied.
        """
        if not cls.is_live_trading_enabled():
            mode = os.environ.get("TRADING_MODE", "PAPER")
            raise LiveTradingSafetyViolation(
                f"SAFETY LOCK ACTIVATED: Real-money live broker execution is blocked. "
                f"Current TRADING_MODE='{mode}'. To enable live trading, you must explicitly set "
                f"TRADING_MODE='LIVE' and LIVE_TRADING_CONFIRMATION='{cls.SAFETY_CONFIRMATION_STRING}'."
            )
