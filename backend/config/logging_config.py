from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler


LOGGER_NAME = "ipo_trading"


def setup_logging(
    log_dir: str | None = None,
    log_level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure structured daily rotating file and console logging.

    Logs to `logs/ipo_trading.log` with daily midnight rollover and
    a 30-day retention policy.
    """
    logger = logging.getLogger(LOGGER_NAME)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Daily rotating file handler
    target_dir = log_dir or os.path.join("logs")
    os.makedirs(target_dir, exist_ok=True)

    log_file_path = os.path.join(target_dir, "ipo_trading.log")
    file_handler = TimedRotatingFileHandler(
        log_file_path,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """Return the configured IPO trading logger or initialize default."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        return setup_logging()
    return logger
