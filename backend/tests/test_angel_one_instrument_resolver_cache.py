import json
import os
import time
from unittest.mock import patch

import pytest
import requests

from backend.collectors.market_data.angel_one_instrument_resolver import (
    AngelOneInstrumentResolver,
)


SAMPLE_INSTRUMENTS = [
    {
        "token": "2885",
        "symbol": "RELIANCE-EQ",
        "name": "RELIANCE",
        "exch_seg": "NSE",
        "instrumenttype": "",
    },
    {
        "token": "1594",
        "symbol": "INFY-EQ",
        "name": "INFOSYS",
        "exch_seg": "NSE",
        "instrumenttype": "",
    },
    {
        "token": "9999",
        "symbol": "HORIZONIND-EQ",
        "name": "HORIZONIND",
        "exch_seg": "NSE",
        "instrumenttype": "",
    },
]


def test_resolver_uses_disk_cache_without_network(tmp_path):
    cache_file = str(tmp_path / "instruments.json")

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_INSTRUMENTS, f)

    resolver = AngelOneInstrumentResolver(cache_path=cache_file)

    with patch("requests.get") as mock_get:
        result = resolver.find("RELIANCE")
        mock_get.assert_not_called()

    assert result["token"] == "2885"
    assert result["symbol"] == "RELIANCE-EQ"


def test_resolver_downloads_and_creates_cache_when_missing(tmp_path):
    cache_file = str(tmp_path / "new_dir" / "instruments.json")
    resolver = AngelOneInstrumentResolver(cache_path=cache_file)

    mock_response = patch("requests.get").start()
    mock_response.return_value.status_code = 200
    mock_response.return_value.json.return_value = SAMPLE_INSTRUMENTS

    try:
        result = resolver.find("INFY")
        assert result["token"] == "1594"
        assert os.path.exists(cache_file)

        with open(cache_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert len(saved) == 3
    finally:
        patch.stopall()


def test_resolver_falls_back_to_stale_cache_on_network_failure(tmp_path):
    cache_file = str(tmp_path / "stale_instruments.json")

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_INSTRUMENTS, f)

    # Set cache mtime to 48 hours ago
    old_time = time.time() - (48 * 3600)
    os.utime(cache_file, (old_time, old_time))

    resolver = AngelOneInstrumentResolver(
        cache_path=cache_file,
        cache_ttl_hours=24,
    )

    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Offline")):
        result = resolver.find("HORIZONIND")

    assert result["token"] == "9999"
    assert result["symbol"] == "HORIZONIND-EQ"


def test_resolver_raises_when_network_fails_and_no_cache(tmp_path):
    cache_file = str(tmp_path / "non_existent.json")
    resolver = AngelOneInstrumentResolver(cache_path=cache_file)

    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Offline")):
        with pytest.raises(requests.exceptions.ConnectionError):
            resolver.find("RELIANCE")


def test_resolver_invalidates_cache_after_morning_cutoff(tmp_path):
    from datetime import datetime, timedelta
    from backend.collectors.market_data.angel_one_instrument_resolver import IST

    cache_file = str(tmp_path / "morning_instruments.json")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_INSTRUMENTS, f)

    # Set cache mtime to 07:00 AM IST today
    now_ist = datetime.now(IST)
    cache_dt = now_ist.replace(hour=7, minute=0, second=0, microsecond=0)
    # Ensure current simulated time is 09:30 AM IST today
    current_dt = now_ist.replace(hour=9, minute=30, second=0, microsecond=0)

    resolver = AngelOneInstrumentResolver(cache_path=cache_file)

    mock_resp = patch("requests.get").start()
    mock_resp.return_value.status_code = 200
    mock_resp.return_value.json.return_value = SAMPLE_INSTRUMENTS

    with patch("os.path.getmtime", return_value=cache_dt.timestamp()), \
         patch("backend.collectors.market_data.angel_one_instrument_resolver.datetime") as mock_dt:
        mock_dt.now.return_value = current_dt
        mock_dt.fromtimestamp = datetime.fromtimestamp

        res = resolver.find("RELIANCE")
        assert res["token"] == "2885"
        mock_resp.assert_called_once()
    patch.stopall()


def test_resolver_on_miss_triggers_remote_refresh(tmp_path):
    cache_file = str(tmp_path / "stale_instruments.json")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_INSTRUMENTS, f)

    resolver = AngelOneInstrumentResolver(cache_path=cache_file)

    new_instruments = SAMPLE_INSTRUMENTS + [
        {
            "token": "766072",
            "symbol": "ARCIL-EQ",
            "name": "ARCIL",
            "exch_seg": "NSE",
            "instrumenttype": "",
        }
    ]

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = new_instruments

        result = resolver.find("ARCIL")
        assert result["token"] == "766072"
        mock_get.assert_called_once()


def test_resolver_auto_heals_when_server_comes_back_online(tmp_path):
    cache_file = str(tmp_path / "fallback_instruments.json")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_INSTRUMENTS, f)

    # Set cache to 48 hours ago
    old_time = time.time() - (48 * 3600)
    os.utime(cache_file, (old_time, old_time))

    resolver = AngelOneInstrumentResolver(cache_path=cache_file)

    # 1. First attempt: network error -> falls back to stale cache safely
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Offline")):
        res1 = resolver.find("RELIANCE")
        assert res1["token"] == "2885"
        assert resolver._is_stale_fallback is True

    # 2. Server recovers! Advance time by 65 seconds (past cooldown)
    resolver._last_fallback_attempt = time.time() - 65

    fresh_remote = SAMPLE_INSTRUMENTS + [
        {
            "token": "766077",
            "symbol": "RENTOMOJO-EQ",
            "name": "RENTOMOJO",
            "exch_seg": "NSE",
            "instrumenttype": "",
        }
    ]

    mock_resp = patch("requests.get").start()
    mock_resp.return_value.status_code = 200
    mock_resp.return_value.json.return_value = fresh_remote

    try:
        res2 = resolver.find("RENTOMOJO")
        assert res2["token"] == "766077"
        assert resolver._is_stale_fallback is False
        mock_resp.assert_called_once()
    finally:
        patch.stopall()


