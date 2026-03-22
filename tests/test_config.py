"""Tests for config module: Settings dataclass and factory functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from trading_advisor.config import Settings, create_storage, load_settings
from trading_advisor.storage import LocalStorage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_VARS = {
    "WEALTHOPS_TIINGO_API_KEY": "tiingo-key",
    "WEALTHOPS_FRED_API_KEY": "fred-key",
    "WEALTHOPS_TELEGRAM_BOT_TOKEN": "bot-token",
    "WEALTHOPS_TELEGRAM_CHAT_ID": "chat-id",
}


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all required env vars via monkeypatch."""
    for key, value in _REQUIRED_VARS.items():
        monkeypatch.setenv(key, value)


# ---------------------------------------------------------------------------
# load_settings — happy path
# ---------------------------------------------------------------------------


def test_load_settings_all_required_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings is created correctly when all required vars are set."""
    _set_required(monkeypatch)
    settings = load_settings()
    assert settings.tiingo_api_key == "tiingo-key"
    assert settings.fred_api_key == "fred-key"
    assert settings.telegram_bot_token == "bot-token"
    assert settings.telegram_chat_id == "chat-id"


def test_load_settings_default_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default values are applied when optional vars are not set."""
    _set_required(monkeypatch)
    # Ensure optional vars are not set
    monkeypatch.delenv("WEALTHOPS_TELEGRAM_HEARTBEAT_CHAT_ID", raising=False)
    monkeypatch.delenv("WEALTHOPS_STORAGE_TYPE", raising=False)
    monkeypatch.delenv("WEALTHOPS_DATA_DIR", raising=False)
    monkeypatch.delenv("WEALTHOPS_S3_BUCKET", raising=False)
    monkeypatch.delenv("WEALTHOPS_TELEGRAM_MODE", raising=False)
    monkeypatch.delenv("WEALTHOPS_LOG_LEVEL", raising=False)

    settings = load_settings()

    assert settings.telegram_heartbeat_chat_id == ""
    assert settings.storage_type == "local"
    assert settings.data_dir == Path("./data")
    assert settings.s3_bucket == ""
    assert settings.telegram_mode == "polling"
    assert settings.log_level == "INFO"


def test_load_settings_optional_vars_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional env vars override defaults when explicitly set."""
    _set_required(monkeypatch)
    monkeypatch.setenv("WEALTHOPS_TELEGRAM_HEARTBEAT_CHAT_ID", "heartbeat-id")
    monkeypatch.setenv("WEALTHOPS_STORAGE_TYPE", "s3")
    monkeypatch.setenv("WEALTHOPS_DATA_DIR", "/tmp/mydata")
    monkeypatch.setenv("WEALTHOPS_S3_BUCKET", "my-bucket")
    monkeypatch.setenv("WEALTHOPS_TELEGRAM_MODE", "webhook")
    monkeypatch.setenv("WEALTHOPS_LOG_LEVEL", "DEBUG")

    settings = load_settings()

    assert settings.telegram_heartbeat_chat_id == "heartbeat-id"
    assert settings.storage_type == "s3"
    assert settings.data_dir == Path("/tmp/mydata")
    assert settings.s3_bucket == "my-bucket"
    assert settings.telegram_mode == "webhook"
    assert settings.log_level == "DEBUG"


def test_load_settings_data_dir_converted_to_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`data_dir` env var string is converted to a Path object."""
    _set_required(monkeypatch)
    monkeypatch.setenv("WEALTHOPS_DATA_DIR", "/some/path/data")

    settings = load_settings()

    assert isinstance(settings.data_dir, Path)
    assert settings.data_dir == Path("/some/path/data")


# ---------------------------------------------------------------------------
# load_settings — error cases
# ---------------------------------------------------------------------------


def test_load_settings_missing_one_required_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing one required var raises ValueError naming that var."""
    _set_required(monkeypatch)
    monkeypatch.delenv("WEALTHOPS_TIINGO_API_KEY")

    with pytest.raises(ValueError, match="TIINGO_API_KEY"):
        load_settings()


def test_load_settings_missing_multiple_required_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing multiple required vars raises ValueError listing all of them."""
    monkeypatch.delenv("WEALTHOPS_TIINGO_API_KEY", raising=False)
    monkeypatch.delenv("WEALTHOPS_FRED_API_KEY", raising=False)
    monkeypatch.delenv("WEALTHOPS_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("WEALTHOPS_TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(ValueError) as exc_info:
        load_settings()

    message = str(exc_info.value)
    assert "TIINGO_API_KEY" in message
    assert "FRED_API_KEY" in message
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "TELEGRAM_CHAT_ID" in message


# ---------------------------------------------------------------------------
# create_storage
# ---------------------------------------------------------------------------


def test_create_storage_returns_local_storage(tmp_path: Path) -> None:
    """`create_storage` returns a LocalStorage for storage_type='local'."""
    settings = Settings(
        tiingo_api_key="t",
        fred_api_key="f",
        telegram_bot_token="b",
        telegram_chat_id="c",
        storage_type="local",
        data_dir=tmp_path,
    )
    backend = create_storage(settings)
    assert isinstance(backend, LocalStorage)


def test_create_storage_raises_for_unknown_type(tmp_path: Path) -> None:
    """`create_storage` raises ValueError for an unknown storage type."""
    settings = Settings(
        tiingo_api_key="t",
        fred_api_key="f",
        telegram_bot_token="b",
        telegram_chat_id="c",
        storage_type="s3",
        data_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="s3"):
        create_storage(settings)
