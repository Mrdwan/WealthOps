"""Logging configuration: rotating file handler + stderr console output."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s \u2014 %(message)s"


def setup_logging(level: str = "INFO", log_dir: Path = Path("logs")) -> None:
    """Configure the trading_advisor logger with rotating file and stderr handlers.

    Creates the log directory if it does not exist, then attaches a
    RotatingFileHandler (writing to ``log_dir/wealthops.log``) and a
    StreamHandler (stderr) to the ``trading_advisor`` logger.  Calling
    this function more than once is safe: existing handlers are removed
    before new ones are added.

    Args:
        level: Logging level name, e.g. ``"INFO"``, ``"DEBUG"``, ``"WARNING"``.
            Case-insensitive.  Defaults to ``"INFO"``.
        log_dir: Directory in which ``wealthops.log`` will be written.
            Created automatically if absent.  Defaults to ``Path("logs")``.
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("trading_advisor")

    # Idempotent: clear any previously attached handlers.
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    logger.setLevel(getattr(logging, level.upper()))
    logger.propagate = False

    formatter = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        log_dir / "wealthops.log",
        maxBytes=5_242_880,
        backupCount=5,
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
