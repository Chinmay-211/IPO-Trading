from datetime import date, datetime
from unittest.mock import Mock

import pytest

from backend.execution.paper_broker import PaperBroker
from backend.services.ipo_session_persistence import (
    IPOSessionPersistence,
)


def test_save_and_load_snapshot_roundtrip(tmp_path):
    storage = IPOSessionPersistence(storage_dir=str(tmp_path))

    data = {
        "date": "2026-08-24",
        "symbols": ["HORIZONIND"],
        "realized_pnl": 1500.0,
    }

    file_path = storage.save_snapshot(data, session_date="2026-08-24")
    assert "session_20260824.json" in file_path

    loaded = storage.load_snapshot("2026-08-24")
    assert loaded is not None
    assert loaded["symbols"] == ["HORIZONIND"]
    assert loaded["realized_pnl"] == 1500.0


def test_restore_broker_state():
    storage = IPOSessionPersistence()
    broker = PaperBroker()

    snapshot = {
        "positions": {
            "HORIZONIND": {
                "symbol": "HORIZONIND",
                "quantity": 10,
                "average_price": 102.5,
            }
        },
        "orders": [
            {
                "symbol": "HORIZONIND",
                "action": "BUY",
                "quantity": 10,
                "price": 102.5,
            }
        ],
        "realized_pnl": 500.0,
    }

    success = storage.restore_broker(broker, snapshot)
    assert success is True

    pos = broker.get_position("HORIZONIND")
    assert pos is not None
    assert pos["quantity"] == 10
    assert pos["average_price"] == 102.5

    orders = broker.get_orders()
    assert len(orders) == 1
    assert orders[0]["side"] == "BUY"

    assert broker.get_realized_pnl() == 500.0


def test_restore_orchestrator_brokers(tmp_path):
    storage = IPOSessionPersistence(storage_dir=str(tmp_path))

    mock_broker = PaperBroker()
    mock_orchestrator = Mock()
    mock_orchestrator.brokers = {"SWIGGY": mock_broker}

    snapshot = {
        "brokers": {
            "SWIGGY": {
                "positions": {
                    "SWIGGY": {
                        "symbol": "SWIGGY",
                        "quantity": 25,
                        "average_price": 420.0,
                    }
                },
                "orders": [
                    {"symbol": "SWIGGY", "action": "BUY", "quantity": 25, "price": 420.0}
                ],
                "realized_pnl": 1250.0,
            }
        }
    }

    storage.save_snapshot(snapshot, session_date="2026-08-24")

    restored = storage.restore_orchestrator(mock_orchestrator, "2026-08-24")
    assert restored is True

    pos = mock_broker.get_position("SWIGGY")
    assert pos is not None
    assert pos["quantity"] == 25
    assert pos["average_price"] == 420.0


def test_load_non_existent_snapshot_returns_none(tmp_path):
    storage = IPOSessionPersistence(storage_dir=str(tmp_path))
    assert storage.load_snapshot("1999-01-01") is None
