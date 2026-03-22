"""Tests for StorageBackend ABC and LocalStorage implementation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trading_advisor.storage import LocalStorage, StorageBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df() -> pd.DataFrame:
    """Return a small DataFrame for roundtrip tests."""
    return pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "close": [1.1, 2.1, 3.1],
        }
    )


def _make_json() -> dict[str, object]:
    """Return a small dict for JSON roundtrip tests."""
    return {"symbol": "XAUUSD", "count": 42, "values": [1.0, 2.0]}


# ---------------------------------------------------------------------------
# ABC contract
# ---------------------------------------------------------------------------


def test_storage_backend_is_abstract() -> None:
    """StorageBackend cannot be instantiated directly."""
    with pytest.raises(TypeError):
        StorageBackend()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# LocalStorage — parquet
# ---------------------------------------------------------------------------


def test_parquet_roundtrip(tmp_path: Path) -> None:
    """Write then read parquet preserves DataFrame contents."""
    storage = LocalStorage(data_dir=tmp_path)
    df = _make_df()
    storage.write_parquet("prices", df)
    result = storage.read_parquet("prices")
    pd.testing.assert_frame_equal(result, df)


def test_read_parquet_missing_raises(tmp_path: Path) -> None:
    """`read_parquet` raises FileNotFoundError for a missing key."""
    storage = LocalStorage(data_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        storage.read_parquet("nonexistent")


# ---------------------------------------------------------------------------
# LocalStorage — JSON
# ---------------------------------------------------------------------------


def test_json_roundtrip(tmp_path: Path) -> None:
    """Write then read JSON preserves dict contents."""
    storage = LocalStorage(data_dir=tmp_path)
    data = _make_json()
    storage.write_json("meta", data)
    result = storage.read_json("meta")
    assert result == data


def test_read_json_missing_raises(tmp_path: Path) -> None:
    """`read_json` raises FileNotFoundError for a missing key."""
    storage = LocalStorage(data_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        storage.read_json("nonexistent")


# ---------------------------------------------------------------------------
# LocalStorage — exists
# ---------------------------------------------------------------------------


def test_exists_false_before_write(tmp_path: Path) -> None:
    """`exists` returns False when neither parquet nor JSON file is present."""
    storage = LocalStorage(data_dir=tmp_path)
    assert storage.exists("prices") is False


def test_exists_true_after_parquet_write(tmp_path: Path) -> None:
    """`exists` returns True after writing a parquet file."""
    storage = LocalStorage(data_dir=tmp_path)
    storage.write_parquet("prices", _make_df())
    assert storage.exists("prices") is True


def test_exists_true_after_json_write(tmp_path: Path) -> None:
    """`exists` returns True after writing a JSON file."""
    storage = LocalStorage(data_dir=tmp_path)
    storage.write_json("meta", _make_json())
    assert storage.exists("meta") is True


# ---------------------------------------------------------------------------
# LocalStorage — nested key paths
# ---------------------------------------------------------------------------


def test_nested_key_creates_subdirectory_parquet(tmp_path: Path) -> None:
    """Nested keys (e.g. ohlcv/XAUUSD_daily) create subdirectories automatically."""
    storage = LocalStorage(data_dir=tmp_path)
    df = _make_df()
    storage.write_parquet("ohlcv/XAUUSD_daily", df)
    expected_path = tmp_path / "ohlcv" / "XAUUSD_daily.parquet"
    assert expected_path.exists()
    result = storage.read_parquet("ohlcv/XAUUSD_daily")
    pd.testing.assert_frame_equal(result, df)


def test_nested_key_creates_subdirectory_json(tmp_path: Path) -> None:
    """Nested keys for JSON create subdirectories automatically."""
    storage = LocalStorage(data_dir=tmp_path)
    data = _make_json()
    storage.write_json("signals/daily", data)
    expected_path = tmp_path / "signals" / "daily.json"
    assert expected_path.exists()
    result = storage.read_json("signals/daily")
    assert result == data
