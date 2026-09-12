from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any

from backend.execution.paper_broker import (
    PaperBroker,
    PaperOrder,
    PaperPosition,
)


class IPOSessionPersistence:
    """
    Persists and recovers intraday IPO paper trading state.

    Ensures that if the trading process crashes or restarts at 11:30 AM,
    active positions, entry prices, filled orders, and realized P&L
    are cleanly restored from disk.
    """

    def __init__(self, storage_dir: str | None = None):
        self.storage_dir = storage_dir or os.path.join("data", "sessions")

    def _get_file_path(self, session_date: date | str) -> str:
        date_str = session_date.strftime("%Y%m%d") if isinstance(session_date, date) else str(session_date).replace("-", "")
        return os.path.join(self.storage_dir, f"session_{date_str}.json")

    def save_snapshot(
        self,
        snapshot_data: dict[str, Any],
        session_date: date | str | None = None,
    ) -> str:
        """Atomically save snapshot data to JSON on disk."""
        target_date = session_date or date.today()
        file_path = self._get_file_path(target_date)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        tmp_path = f"{file_path}.tmp"

        def _json_serial(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, default=_json_serial, indent=2)

        # Atomic replace
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rename(tmp_path, file_path)

        return file_path

    def load_snapshot(self, session_date: date | str) -> dict[str, Any] | None:
        """Load session snapshot from disk if present."""
        file_path = self._get_file_path(session_date)
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def restore_broker(
        self,
        broker: PaperBroker,
        broker_snapshot: dict[str, Any],
    ) -> bool:
        """Rehydrate a PaperBroker instance with saved orders, positions, and P&L."""
        if not isinstance(broker, PaperBroker) or not isinstance(broker_snapshot, dict):
            return False

        # Restore positions
        positions = broker_snapshot.get("positions") or {}
        for sym, pos_data in positions.items():
            if pos_data and isinstance(pos_data, dict):
                broker.positions[sym] = PaperPosition(
                    symbol=pos_data.get("symbol", sym),
                    quantity=int(pos_data.get("quantity", 0)),
                    average_price=float(pos_data.get("average_price", 0.0)),
                )

        # Restore orders
        orders = broker_snapshot.get("orders") or []
        restored_orders = []
        for o in orders:
            if isinstance(o, dict):
                ts = o.get("timestamp")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except ValueError:
                        ts = datetime.now()
                elif not isinstance(ts, datetime):
                    ts = datetime.now()

                restored_orders.append(
                    PaperOrder(
                        order_id=o.get("order_id", "PAPER-RESTORED"),
                        symbol=o.get("symbol", ""),
                        side=o.get("side") or o.get("action", "BUY"),
                        quantity=int(o.get("quantity", 0)),
                        price=float(o.get("price", 0.0)),
                        timestamp=ts,
                        status=o.get("status", "FILLED"),
                    )
                )
        broker.orders = restored_orders

        # Restore realized P&L
        broker.realized_pnl = float(broker_snapshot.get("realized_pnl", 0.0))

        return True

    def extract_orchestrator_snapshot(self, orchestrator: Any) -> dict[str, Any]:
        """Extract serializable snapshot from an active IPOListingDayOrchestrator."""
        brokers_data: dict[str, Any] = {}

        for sym, broker in getattr(orchestrator, "brokers", {}).items():
            brokers_data[sym] = {
                "positions": {sym: broker.get_position(sym)},
                "orders": broker.get_orders(),
                "realized_pnl": broker.get_realized_pnl(),
            }

        return {
            "timestamp": datetime.now().isoformat(),
            "registered_symbols": list(getattr(orchestrator, "brokers", {}).keys()),
            "token_to_symbol": getattr(orchestrator, "token_to_symbol", {}),
            "brokers": brokers_data,
        }

    def restore_orchestrator(self, orchestrator: Any, session_date: date | str) -> bool:
        """Restore all broker states in an orchestrator from saved snapshot."""
        snapshot = self.load_snapshot(session_date)
        if not snapshot:
            return False

        brokers_data = snapshot.get("brokers") or {}
        for sym, broker in getattr(orchestrator, "brokers", {}).items():
            if sym in brokers_data:
                self.restore_broker(broker, brokers_data[sym])

        return True
