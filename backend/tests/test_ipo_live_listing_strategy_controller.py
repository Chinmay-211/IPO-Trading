from datetime import datetime, timedelta

import pytest

from backend.services.ipo_live_listing_strategy_controller import (
    IPOLiveListingStrategyController,
)


def candle(
    minute,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
):
    return {
        "symbol": "TESTIPO",
        "timestamp": datetime(2026, 8, 31, 9, minute),
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "close_price": close_price,
        "volume": volume,
    }


def build_entry_sequence():
    """
    Opening = 100

    First 5 candles:
        observation only

    Candle 6:
        2% dip

    Candle 7:
        recovery above 100 + 1.5x volume

    Candle 8:
        next candle OPEN = 101
        → BUY
    """

    return [
        candle(15, 100, 101, 99.5, 100, 1000),
        candle(16, 100, 101, 99.5, 100, 1000),
        candle(17, 100, 101, 99.5, 100, 1000),
        candle(18, 100, 101, 99.5, 100, 1000),
        candle(19, 100, 101, 99.5, 100, 1000),

        candle(20, 99, 99.5, 98, 98.5, 1000),

        candle(21, 100, 102, 99.8, 101, 1600),

        candle(22, 101, 101.5, 100.8, 101.2, 1000),
    ]


def test_no_signal_before_five_observation_candles():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    for item in build_entry_sequence()[:4]:
        result = controller.process_candle(item)

        assert result is None

    assert controller.get_state()["candles"] == 4


def test_detects_two_percent_dip():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    for item in build_entry_sequence()[:6]:
        controller.process_candle(item)

    state = controller.get_state()

    assert state["opening_price"] == 100
    assert state["dip_low"] == 98


def test_volume_confirmation_sets_pending_entry():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    for item in build_entry_sequence()[:7]:
        result = controller.process_candle(item)

        assert result is None

    state = controller.get_state()

    assert state["confirmed"] is True
    assert state["entry_pending"] is True


def test_buy_occurs_on_next_candle_open():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    result = None

    for item in build_entry_sequence():
        result = controller.process_candle(item)

    assert result is not None
    assert result["action"] == "BUY"
    assert result["symbol"] == "TESTIPO"
    assert result["quantity"] == 10
    assert result["price"] == 101.0

    state = controller.get_state()

    assert state["position_open"] is True
    assert state["entry_price"] == 101.0


def test_stop_loss_generates_sell():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    sequence = build_entry_sequence()

    for item in sequence:
        controller.process_candle(item)

    result = controller.process_candle(
        candle(
            23,
            101,
            101.2,
            97.5,
            98,
            1000,
        )
    )

    assert result is not None
    assert result["action"] == "SELL"
    assert result["outcome"] == "STOP_LOSS"
    assert result["price"] == 98.0

    assert controller.get_state()["position_open"] is False
    assert controller.get_state()["closed"] is True


def test_target_generates_sell():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    sequence = build_entry_sequence()

    for item in sequence:
        controller.process_candle(item)

    state = controller.get_state()

    target = state["target_price"]

    result = controller.process_candle(
        candle(
            23,
            101,
            target + 0.5,
            100.5,
            target,
            1000,
        )
    )

    assert result is not None
    assert result["action"] == "SELL"
    assert result["outcome"] == "TARGET"
    assert result["price"] == target

    assert controller.get_state()["position_open"] is False
    assert controller.get_state()["closed"] is True


def test_screening_failure_produces_no_trade():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
        screening_passed=False,
    )

    result = controller.process_candle(
        candle(
            15,
            100,
            101,
            99,
            100,
            1000,
        )
    )

    assert result is not None
    assert result["action"] == "NO_TRADE"
    assert result["symbol"] == "TESTIPO"
    assert controller.get_state()["position_open"] is False


def test_no_duplicate_entry_after_buy():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    sequence = build_entry_sequence()

    buy = None

    for item in sequence:
        buy = controller.process_candle(item)

    assert buy["action"] == "BUY"

    next_result = controller.process_candle(
        candle(
            23,
            101,
            102,
            100,
            101,
            1000,
        )
    )

    assert next_result is None
    assert controller.get_state()["position_open"] is True


def test_reset_clears_strategy_state():
    controller = IPOLiveListingStrategyController(
        symbol="TESTIPO",
        quantity=10,
    )

    for item in build_entry_sequence():
        controller.process_candle(item)

    assert controller.get_state()["candles"] == 8

    controller.reset()

    state = controller.get_state()

    assert state["candles"] == 0
    assert state["opening_price"] is None
    assert state["dip_low"] is None
    assert state["confirmed"] is False
    assert state["entry_pending"] is False
    assert state["position_open"] is False
    assert state["closed"] is False
    assert state["last_decision"] is None