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
