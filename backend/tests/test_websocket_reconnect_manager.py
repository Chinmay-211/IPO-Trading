from unittest.mock import Mock

import pytest

from backend.services.websocket_reconnect_manager import (
    WebSocketReconnectManager,
)


def test_exponential_backoff_calculation_and_cap():
    manager = WebSocketReconnectManager(
        base_delay=1.0,
        max_delay=10.0,
        backoff_factor=2.0,
        max_retries=5,
    )

    # 1.0 * 2^0 = 1.0
    assert manager.get_backoff_delay(0) == 1.0
    # 1.0 * 2^1 = 2.0
    assert manager.get_backoff_delay(1) == 2.0
    # 1.0 * 2^2 = 4.0
    assert manager.get_backoff_delay(2) == 4.0
    # 1.0 * 2^3 = 8.0
    assert manager.get_backoff_delay(3) == 8.0
    # 1.0 * 2^4 = 16.0 -> capped at max_delay 10.0
    assert manager.get_backoff_delay(4) == 10.0


def test_successful_reconnect_resets_counter_and_resubscribes():
    manager = WebSocketReconnectManager(max_retries=3)

    mock_connect = Mock()
    mock_subscribe = Mock()
    mock_sleep = Mock()

    tokens = ["2885", "1594"]

    success = manager.attempt_reconnect(
        connect_fn=mock_connect,
        subscribe_fn=mock_subscribe,
        tokens=tokens,
        sleep_fn=mock_sleep,
    )

    assert success is True
    assert manager.retry_count == 0
    assert manager.total_reconnects == 1
    mock_sleep.assert_called_once_with(1.0)
    mock_connect.assert_called_once()
    mock_subscribe.assert_called_once_with(tokens)


def test_failed_reconnect_increments_retry_count():
    manager = WebSocketReconnectManager(max_retries=3)

    mock_connect = Mock(side_effect=ConnectionError("Socket dead"))
    mock_sleep = Mock()

    success = manager.attempt_reconnect(
        connect_fn=mock_connect,
        sleep_fn=mock_sleep,
    )

    assert success is False
    assert manager.retry_count == 1
    assert "Socket dead" in str(manager.last_error)


def test_exhausting_max_retries_raises_runtime_error():
    manager = WebSocketReconnectManager(max_retries=2)
    manager.retry_count = 2

    mock_connect = Mock()
    mock_sleep = Mock()

    with pytest.raises(RuntimeError, match="Maximum reconnection attempts"):
        manager.attempt_reconnect(
            connect_fn=mock_connect,
            sleep_fn=mock_sleep,
        )
