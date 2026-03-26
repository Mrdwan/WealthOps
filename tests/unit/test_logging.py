"""Tests for logging configuration."""

import logging
from collections.abc import Generator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from trading_advisor.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_logger() -> Generator[None, None, None]:
    """Reset the trading_advisor logger after each test to prevent cross-test pollution."""
    yield
    logger = logging.getLogger("trading_advisor")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.setLevel(logging.WARNING)


def test_log_dir_created(tmp_path: Path) -> None:
    """setup_logging creates the log directory and log file."""
    log_dir = tmp_path / "logs"
    setup_logging(log_dir=log_dir)
    assert log_dir.exists()
    assert (log_dir / "wealthops.log").exists()


def test_message_written_to_file(tmp_path: Path) -> None:
    """Messages logged at INFO level are written to the log file."""
    log_dir = tmp_path / "logs"
    setup_logging(log_dir=log_dir)
    logger = logging.getLogger("trading_advisor")
    logger.info("test message")
    for h in logger.handlers:
        h.flush()
    text = (log_dir / "wealthops.log").read_text()
    assert "test message" in text
    assert "INFO" in text


def test_rotating_handler_config(tmp_path: Path) -> None:
    """RotatingFileHandler is configured with correct maxBytes and backupCount."""
    setup_logging(log_dir=tmp_path)
    rfh = [
        h
        for h in logging.getLogger("trading_advisor").handlers
        if isinstance(h, RotatingFileHandler)
    ]
    assert len(rfh) == 1
    assert rfh[0].maxBytes == 5_242_880
    assert rfh[0].backupCount == 5


def test_idempotent_no_duplicate_handlers(tmp_path: Path) -> None:
    """Calling setup_logging twice does not duplicate handlers."""
    setup_logging(log_dir=tmp_path)
    setup_logging(log_dir=tmp_path)
    handlers = logging.getLogger("trading_advisor").handlers
    assert len(handlers) == 2


def test_custom_level_respected(tmp_path: Path) -> None:
    """The logger level is set to the requested level."""
    setup_logging(level="DEBUG", log_dir=tmp_path)
    logger = logging.getLogger("trading_advisor")
    assert logger.level == logging.DEBUG


def test_warning_level_filters_info(tmp_path: Path) -> None:
    """INFO messages are suppressed when the logger level is WARNING."""
    log_dir = tmp_path / "logs"
    setup_logging(level="WARNING", log_dir=log_dir)
    logger = logging.getLogger("trading_advisor")
    logger.info("should not appear")
    logger.warning("should appear")
    for h in logger.handlers:
        h.flush()
    text = (log_dir / "wealthops.log").read_text()
    assert "should not appear" not in text
    assert "should appear" in text
