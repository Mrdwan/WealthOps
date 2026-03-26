"""Configuration: loads .env secrets and constructs runtime dependencies.

Exposes a `Settings` frozen dataclass populated from environment variables
(with a `WEALTHOPS_` prefix), and factory helpers for storage backends.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import dotenv

from trading_advisor.storage.base import StorageBackend
from trading_advisor.storage.local import LocalStorage


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables.

    Args:
        tiingo_api_key: API key for the Tiingo market data provider.
        fred_api_key: API key for the FRED economic data provider.
        telegram_bot_token: Telegram bot token for sending messages.
        telegram_chat_id: Primary Telegram chat ID for trade signals.
        telegram_heartbeat_chat_id: Optional chat ID for heartbeat messages.
        storage_type: Backend type identifier (e.g. ``"local"``).
        data_dir: Root directory used by the local storage backend.
        s3_bucket: S3 bucket name for the S3 storage backend.
        telegram_mode: Telegram polling mode (``"polling"`` or ``"webhook"``).
        log_level: Python logging level name (e.g. ``"INFO"``, ``"DEBUG"``).
        guards_enabled: Maps guard names to on/off. Empty dict = all enabled.
    """

    tiingo_api_key: str
    fred_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_heartbeat_chat_id: str = field(default="")
    storage_type: str = field(default="local")
    data_dir: Path = field(default=Path("./data"))
    s3_bucket: str = field(default="")
    telegram_mode: str = field(default="polling")
    log_level: str = field(default="INFO")
    guards_enabled: dict[str, bool] = field(default_factory=dict)


def _parse_guards_enabled(raw: str) -> dict[str, bool]:
    """Parse a JSON string into a guard-enable mapping.

    Args:
        raw: JSON string (e.g. ``'{"MacroGate": false}'``).

    Returns:
        A dictionary mapping guard names to booleans.

    Raises:
        ValueError: If *raw* is not valid JSON or not a JSON object with
            boolean values.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"WEALTHOPS_GUARDS_ENABLED must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"WEALTHOPS_GUARDS_ENABLED must be a JSON object, got {type(parsed).__name__}"
        )
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, bool):
            raise ValueError(
                f"WEALTHOPS_GUARDS_ENABLED values must be booleans, got {key!r}: {value!r}"
            )
    return dict(parsed)


def load_settings() -> Settings:
    """Load application settings from environment variables.

    Calls ``dotenv.load_dotenv()`` first to populate the environment from a
    ``.env`` file if one exists.  All variables must be prefixed with
    ``WEALTHOPS_`` (e.g. ``WEALTHOPS_TIINGO_API_KEY``).

    Returns:
        A fully populated :class:`Settings` instance.

    Raises:
        ValueError: If any required environment variables are missing.  The
            error message lists *all* missing variables at once.
    """
    dotenv.load_dotenv()

    _required = [
        "TIINGO_API_KEY",
        "FRED_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ]

    missing = [name for name in _required if not os.environ.get(f"WEALTHOPS_{name}")]
    if missing:
        raise ValueError("Missing required environment variables: " + ", ".join(missing))

    data_dir_raw = os.environ.get("WEALTHOPS_DATA_DIR", "./data")

    return Settings(
        tiingo_api_key=os.environ["WEALTHOPS_TIINGO_API_KEY"],
        fred_api_key=os.environ["WEALTHOPS_FRED_API_KEY"],
        telegram_bot_token=os.environ["WEALTHOPS_TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=os.environ["WEALTHOPS_TELEGRAM_CHAT_ID"],
        telegram_heartbeat_chat_id=os.environ.get("WEALTHOPS_TELEGRAM_HEARTBEAT_CHAT_ID", ""),
        storage_type=os.environ.get("WEALTHOPS_STORAGE_TYPE", "local"),
        data_dir=Path(data_dir_raw),
        s3_bucket=os.environ.get("WEALTHOPS_S3_BUCKET", ""),
        telegram_mode=os.environ.get("WEALTHOPS_TELEGRAM_MODE", "polling"),
        log_level=os.environ.get("WEALTHOPS_LOG_LEVEL", "INFO"),
        guards_enabled=_parse_guards_enabled(
            os.environ.get("WEALTHOPS_GUARDS_ENABLED", "{}"),
        ),
    )


def create_storage(settings: Settings) -> StorageBackend:
    """Instantiate and return the configured storage backend.

    Args:
        settings: Application settings that determine which backend to create.

    Returns:
        A concrete :class:`~trading_advisor.storage.base.StorageBackend`
        instance matching ``settings.storage_type``.

    Raises:
        ValueError: If ``settings.storage_type`` is not a recognised type.
    """
    if settings.storage_type == "local":
        return LocalStorage(settings.data_dir)
    raise ValueError(f"Unknown storage type: {settings.storage_type!r}. Supported types: 'local'.")
