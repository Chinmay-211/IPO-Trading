import logging
import os

from backend.config.logging_config import (
    LOGGER_NAME,
    get_logger,
    setup_logging,
)


def test_logging_setup_creates_log_file(tmp_path):
    log_dir = str(tmp_path / "test_logs")

    # Clear handlers on the logger for testing
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()

    active_logger = setup_logging(log_dir=log_dir, log_level=logging.INFO)

    active_logger.info("Test event: IPO trading session initialized")

    log_file = os.path.join(log_dir, "ipo_trading.log")
    assert os.path.exists(log_file)

    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Test event: IPO trading session initialized" in content
    assert "[INFO]" in content

    # Clean up handlers
    for handler in active_logger.handlers[:]:
        handler.close()
        active_logger.removeHandler(handler)


def test_get_logger_returns_active_logger():
    logger = get_logger()
    assert logger.name == LOGGER_NAME
