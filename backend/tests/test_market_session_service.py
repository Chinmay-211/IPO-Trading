from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from backend.services.market_session_service import (
    MarketSessionService,
)


IST = ZoneInfo("Asia/Kolkata")


def test_before_market_open():
    service = MarketSessionService()

    timestamp = datetime(
        2026,
        8,
        31,
        9,
        14,
        tzinfo=IST,
    )

    assert (
        service.is_market_open(timestamp)
        is False
    )

    assert (
        service.get_session_state(timestamp)
        == "PRE_OPEN"
    )


def test_market_open_at_0915():
    service = MarketSessionService()

    timestamp = datetime(
        2026,
        8,
        31,
        9,
        15,
        tzinfo=IST,
    )

    assert (
        service.is_market_open(timestamp)
        is True
    )

    assert (
        service.get_session_state(timestamp)
        == "OPEN"
    )


def test_market_open_during_session():
    service = MarketSessionService()

    timestamp = datetime(
        2026,
        8,
        31,
        12,
        30,
        tzinfo=IST,
    )

    assert (
        service.is_market_open(timestamp)
        is True
    )


def test_market_close_at_1530():
    service = MarketSessionService()

    timestamp = datetime(
        2026,
        8,
        31,
        15,
        30,
        tzinfo=IST,
    )

    assert (
        service.is_market_open(timestamp)
        is False
    )

    assert (
        service.get_session_state(timestamp)
        == "CLOSED"
    )


def test_after_market_close():
    service = MarketSessionService()

    timestamp = datetime(
        2026,
        8,
        31,
        16,
        0,
        tzinfo=IST,
    )

    assert (
        service.is_market_open(timestamp)
        is False
    )

    assert (
        service.is_after_market_close(
            timestamp
        )
        is True
    )


def test_before_open_helper():
    service = MarketSessionService()

    timestamp = datetime(
        2026,
        8,
        31,
        8,
        59,
        tzinfo=IST,
    )

    assert (
        service.is_before_market_open(
            timestamp
        )
        is True
    )


def test_naive_datetime_is_treated_as_ist():
    service = MarketSessionService()

    timestamp = datetime(
        2026,
        8,
        31,
        10,
        0,
    )

    assert (
        service.is_market_open(timestamp)
        is True
    )


def test_utc_timestamp_is_converted_to_ist():
    service = MarketSessionService()

    # 04:00 UTC = 09:30 IST
    timestamp = datetime(
        2026,
        8,
        31,
        4,
        0,
        tzinfo=ZoneInfo("UTC"),
    )

    assert (
        service.is_market_open(timestamp)
        is True
    )


def test_invalid_timestamp_is_rejected():
    service = MarketSessionService()

    with pytest.raises(TypeError):
        service.is_market_open(
            "2026-08-31 10:00"
        )


def test_custom_session_window():
    service = MarketSessionService(
        market_open=time(10, 0),
        market_close=time(14, 0),
    )

    timestamp = datetime(
        2026,
        8,
        31,
        10,
        30,
        tzinfo=IST,
    )

    assert (
        service.is_market_open(timestamp)
        is True
    )