from __future__ import annotations

from unittest.mock import Mock

from backend.collectors.market_data.angel_one_candle_source import (
    AngelOneCandleSource,
)


def make_source() -> AngelOneCandleSource:
    """
    Create the candle source without making a real
    Angel One API request.
    """

    source = AngelOneCandleSource()

    source._login = Mock()

    source.resolver.find = Mock(
        return_value={
            "token": "2885",
        }
    )

    source.smart_api = Mock()

    source.smart_api.getCandleData = Mock(
        return_value={
            "status": True,
            "data": [
                [
                    "2026-08-27T09:15:00+05:30",
                    "100.00",
                    "102.00",
                    "99.50",
                    "101.50",
                    "10000",
                ],
                [
                    "2026-08-27T09:16:00+05:30",
                    "101.50",
                    "103.00",
                    "101.00",
                    "102.50",
                    "12000",
                ],
            ],
        }
    )

    return source


def test_angel_one_candle_source():
    source = make_source()

    candles = source.fetch(
        symbol="RELIANCE-EQ",
        listing_date="2026-08-27",
        interval="ONE_MINUTE",
    )

    assert isinstance(candles, list)
    assert len(candles) == 2

    candle = candles[0]

    assert candle["timestamp"] == (
        "2026-08-27T09:15:00+05:30"
    )

    assert candle["open_price"] == 100.0
    assert candle["high_price"] == 102.0
    assert candle["low_price"] == 99.5
    assert candle["close_price"] == 101.5
    assert candle["volume"] == 10000


def test_angel_one_candle_source_builds_correct_request():
    source = make_source()

    source.fetch(
        symbol="RELIANCE-EQ",
        listing_date="2026-08-27",
        interval="ONE_MINUTE",
    )

    source._login.assert_called_once()

    source.resolver.find.assert_called_once_with(
        symbol="RELIANCE-EQ",
        exchange="NSE",
    )

    source.smart_api.getCandleData.assert_called_once_with(
        {
            "exchange": "NSE",
            "symboltoken": "2885",
            "interval": "ONE_MINUTE",
            "fromdate": "2026-08-27 00:00",
            "todate": "2026-08-28 00:00",
        }
    )


def test_angel_one_candle_source_empty_response():
    source = make_source()

    source.smart_api.getCandleData.return_value = {
        "status": True,
        "data": [],
    }

    candles = source.fetch(
        symbol="RELIANCE-EQ",
        listing_date="2026-08-27",
        interval="ONE_MINUTE",
    )

    assert candles == []


def test_angel_one_candle_source_rejected_response():
    source = make_source()

    source.smart_api.getCandleData.return_value = {
        "status": False,
        "data": None,
    }

    try:
        source.fetch(
            symbol="RELIANCE-EQ",
            listing_date="2026-08-27",
            interval="ONE_MINUTE",
        )
    except RuntimeError as exc:
        assert (
            "historical data request was rejected"
            in str(exc)
        )
        return

    raise AssertionError(
        "Expected RuntimeError for rejected response."
    )


def test_angel_one_candle_source_api_exception():
    source = make_source()

    source.smart_api.getCandleData.side_effect = (
        Exception("simulated API failure")
    )

    try:
        source.fetch(
            symbol="RELIANCE-EQ",
            listing_date="2026-08-27",
            interval="ONE_MINUTE",
        )
    except RuntimeError as exc:
        assert (
            "historical data request could not be completed"
            in str(exc)
        )
        return

    raise AssertionError(
        "Expected RuntimeError for API failure."
    )


def test_angel_one_candle_source_converts_numeric_values():
    source = make_source()

    source.smart_api.getCandleData.return_value = {
        "status": True,
        "data": [
            [
                "2026-08-27T09:15:00+05:30",
                "100",
                "105",
                "98",
                "103",
                "2500",
            ]
        ],
    }

    candles = source.fetch(
        symbol="TEST-EQ",
        listing_date="2026-08-27",
        interval="ONE_MINUTE",
    )

    candle = candles[0]

    assert isinstance(
        candle["open_price"],
        float,
    )

    assert isinstance(
        candle["high_price"],
        float,
    )

    assert isinstance(
        candle["low_price"],
        float,
    )

    assert isinstance(
        candle["close_price"],
        float,
    )

    assert isinstance(
        candle["volume"],
        int,
    )