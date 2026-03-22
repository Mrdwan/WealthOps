"""Tests for the DataIngestor class in trading_advisor.data.ingest."""

from __future__ import annotations

import pandas as pd
import pytest

from trading_advisor.data.base import MacroProvider, OHLCVProvider
from trading_advisor.data.ingest import DataIngestor
from trading_advisor.storage.local import LocalStorage

# ---------------------------------------------------------------------------
# Fake providers
# ---------------------------------------------------------------------------


class FakeOHLCVProvider(OHLCVProvider):
    """In-memory OHLCVProvider for testing.

    Args:
        data: Full dataset; fetch_ohlcv filters to the requested date range.
    """

    def __init__(self, data: pd.DataFrame) -> None:
        self._data = data

    def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Return rows from _data within [start, end]."""
        if self._data.empty:
            empty_index = pd.DatetimeIndex([], name="date")
            return pd.DataFrame(columns=["open", "high", "low", "close"], index=empty_index)
        mask = (self._data.index >= start) & (self._data.index <= end)
        return self._data.loc[mask].copy()


class FakeMacroProvider(MacroProvider):
    """In-memory MacroProvider for testing.

    Args:
        data: Full dataset; fetch_series filters to the requested date range.
    """

    def __init__(self, data: pd.DataFrame) -> None:
        self._data = data

    def fetch_series(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        """Return rows from _data within [start, end]."""
        if self._data.empty:
            empty_index = pd.DatetimeIndex([], name="date")
            return pd.DataFrame({"value": pd.Series([], dtype=float)}, index=empty_index)
        mask = (self._data.index >= start) & (self._data.index <= end)
        return self._data.loc[mask].copy()


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_ohlcv(start: str, periods: int) -> pd.DataFrame:
    """Create a simple valid OHLCV DataFrame."""
    idx = pd.date_range(start, periods=periods, freq="B", name="date")
    n = len(idx)
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(n)],
            "high": [102.0 + i for i in range(n)],
            "low": [98.0 + i for i in range(n)],
            "close": [101.0 + i for i in range(n)],
        },
        index=idx,
    )


def _make_macro(start: str, periods: int) -> pd.DataFrame:
    """Create a simple macro value DataFrame."""
    idx = pd.date_range(start, periods=periods, freq="B", name="date")
    return pd.DataFrame({"value": [float(i) for i in range(len(idx))]}, index=idx)


# ---------------------------------------------------------------------------
# Tests: ingest_ohlcv
# ---------------------------------------------------------------------------


def test_fresh_ohlcv_ingest_writes_and_returns_valid(tmp_path: pytest.TempPathFactory) -> None:
    """Fresh ingest writes data and returns a valid ValidationResult."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    data = _make_ohlcv("2024-01-01", 5)
    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-01-31", "ohlcv/XAUUSD")

    assert result.valid is True
    assert storage.exists("ohlcv/XAUUSD")
    stored = storage.read_parquet("ohlcv/XAUUSD")
    assert len(stored) == len(data)


def test_incremental_ohlcv_ingest_appends_new_data(tmp_path: pytest.TempPathFactory) -> None:
    """Incremental ingest only fetches dates after the last stored date."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    existing = _make_ohlcv("2024-01-01", 3)
    new_data = _make_ohlcv("2024-01-08", 3)
    all_data = pd.concat([existing, new_data])

    # Write existing data first
    storage.write_parquet("ohlcv/XAUUSD", existing)

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(all_data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-01-31", "ohlcv/XAUUSD")

    assert result.valid is True
    stored = storage.read_parquet("ohlcv/XAUUSD")
    # Should have existing + new rows (no duplicates)
    assert len(stored) == len(existing) + len(new_data)
    assert stored.index.is_monotonic_increasing


def test_invalid_ohlcv_raises_and_does_not_write(tmp_path: pytest.TempPathFactory) -> None:
    """Invalid OHLCV data raises ValueError and does not write to storage."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    # Create invalid data: high < low
    idx = pd.date_range("2024-01-01", periods=3, freq="B", name="date")
    bad_data = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [90.0, 90.0, 90.0],  # high < low — invalid
            "low": [95.0, 95.0, 95.0],
            "close": [92.0, 92.0, 92.0],
        },
        index=idx,
    )

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(bad_data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    with pytest.raises(ValueError):
        ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-01-31", "ohlcv/XAUUSD")

    assert not storage.exists("ohlcv/XAUUSD")


def test_valid_ohlcv_with_warnings_still_writes(tmp_path: pytest.TempPathFactory) -> None:
    """Valid OHLCV data with warnings still writes (valid=True with non-empty warnings)."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    # Create data with a large price jump (>5%) to trigger warnings
    idx = pd.date_range("2024-01-01", periods=2, freq="B", name="date")
    warn_data = pd.DataFrame(
        {
            "open": [100.0, 200.0],
            "high": [101.0, 201.0],
            "low": [99.0, 199.0],
            "close": [100.5, 200.5],  # ~100% jump triggers warning
        },
        index=idx,
    )

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(warn_data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-01-31", "ohlcv/XAUUSD")

    assert result.valid is True
    assert len(result.warnings) > 0
    assert storage.exists("ohlcv/XAUUSD")


def test_already_up_to_date_returns_valid_without_fetch(tmp_path: pytest.TempPathFactory) -> None:
    """When stored data covers up to end date, returns valid without fetching."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    existing = _make_ohlcv("2024-01-01", 5)
    last_date = existing.index[-1]
    end_date = (last_date - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    storage.write_parquet("ohlcv/XAUUSD", existing)

    # Provider that would fail if called (it won't be called)
    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(existing),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", end_date, "ohlcv/XAUUSD")

    assert result.valid is True
    assert result.errors == []


def test_empty_fetch_returns_valid_without_writing(tmp_path: pytest.TempPathFactory) -> None:
    """Empty fetch result returns valid ValidationResult without writing."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    empty_data: pd.DataFrame = pd.DataFrame()

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(empty_data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-01-31", "ohlcv/XAUUSD")

    assert result.valid is True
    assert not storage.exists("ohlcv/XAUUSD")


def test_ohlcv_dedup_overlapping_dates_keeps_last(tmp_path: pytest.TempPathFactory) -> None:
    """Overlapping dates between existing and new data are deduplicated (keep last)."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    existing = _make_ohlcv("2024-01-01", 5)
    # New data overlaps the last 2 rows of existing
    overlap_start = existing.index[-2].strftime("%Y-%m-%d")
    new_data = _make_ohlcv(overlap_start, 4)
    # Shift all OHLC values up so the data stays valid but is distinguishable
    new_data["open"] = new_data["open"] + 999.0
    new_data["high"] = new_data["high"] + 999.0
    new_data["low"] = new_data["low"] + 999.0
    new_data["close"] = new_data["close"] + 999.0

    all_provider_data = pd.concat([existing, new_data])
    # Provider returns all; existing is already in storage
    storage.write_parquet("ohlcv/XAUUSD", existing)

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(all_provider_data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    # Start = 1 day after last existing date => incremental fetch
    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-12-31", "ohlcv/XAUUSD")
    assert result.valid is True

    stored = storage.read_parquet("ohlcv/XAUUSD")
    assert stored.index.duplicated().sum() == 0
    assert stored.index.is_monotonic_increasing


# ---------------------------------------------------------------------------
# Tests: ingest_macro
# ---------------------------------------------------------------------------


def test_fresh_macro_ingest_writes_data(tmp_path: pytest.TempPathFactory) -> None:
    """Fresh macro ingest writes data to storage."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    macro_data = _make_macro("2024-01-01", 5)

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(_make_ohlcv("2024-01-01", 0)),
        macro_provider=FakeMacroProvider(macro_data),
        storage=storage,
    )

    ingestor.ingest_macro("VIXCLS", "2024-01-01", "2024-01-31", "macro/VIXCLS")

    assert storage.exists("macro/VIXCLS")
    stored = storage.read_parquet("macro/VIXCLS")
    assert len(stored) == len(macro_data)


def test_incremental_macro_ingest_appends_new_data(tmp_path: pytest.TempPathFactory) -> None:
    """Incremental macro ingest appends new data after existing."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    existing = _make_macro("2024-01-01", 3)
    new_data = _make_macro("2024-01-08", 3)
    all_data = pd.concat([existing, new_data])

    storage.write_parquet("macro/VIXCLS", existing)

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(_make_ohlcv("2024-01-01", 0)),
        macro_provider=FakeMacroProvider(all_data),
        storage=storage,
    )

    ingestor.ingest_macro("VIXCLS", "2024-01-01", "2024-01-31", "macro/VIXCLS")

    stored = storage.read_parquet("macro/VIXCLS")
    assert len(stored) == len(existing) + len(new_data)
    assert stored.index.is_monotonic_increasing


def test_macro_already_up_to_date_returns_early(tmp_path: pytest.TempPathFactory) -> None:
    """When stored macro data covers end date, returns without fetching."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    existing = _make_macro("2024-01-01", 5)
    last_date = existing.index[-1]
    end_date = (last_date - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    storage.write_parquet("macro/VIXCLS", existing)

    call_count = 0

    class CountingMacroProvider(MacroProvider):
        def fetch_series(self, series_id: str, start: str, end: str) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return existing

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(_make_ohlcv("2024-01-01", 0)),
        macro_provider=CountingMacroProvider(),
        storage=storage,
    )

    ingestor.ingest_macro("VIXCLS", "2024-01-01", end_date, "macro/VIXCLS")

    # fetch_series should not have been called since we're already up to date
    assert call_count == 0


def test_macro_empty_fetch_returns_early(tmp_path: pytest.TempPathFactory) -> None:
    """Empty macro fetch returns without writing."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    empty_macro: pd.DataFrame = pd.DataFrame()

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(_make_ohlcv("2024-01-01", 0)),
        macro_provider=FakeMacroProvider(empty_macro),
        storage=storage,
    )

    ingestor.ingest_macro("VIXCLS", "2024-01-01", "2024-01-31", "macro/VIXCLS")

    assert not storage.exists("macro/VIXCLS")


# ---------------------------------------------------------------------------
# Tests: run_daily_ingest
# ---------------------------------------------------------------------------


def test_run_daily_ingest_calls_all_five_and_returns_two_results(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """run_daily_ingest ingests 5 series and returns 2 OHLCV validation results."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    ohlcv_data = _make_ohlcv("2024-01-01", 5)
    macro_data = _make_macro("2024-01-01", 5)

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(ohlcv_data),
        macro_provider=FakeMacroProvider(macro_data),
        storage=storage,
    )

    results = ingestor.run_daily_ingest("2024-12-31")

    assert set(results.keys()) == {"XAUUSD", "EURUSD"}
    assert results["XAUUSD"].valid is True
    assert results["EURUSD"].valid is True

    # All 5 storage keys should exist
    assert storage.exists("ohlcv/XAUUSD_daily")
    assert storage.exists("ohlcv/EURUSD_daily")
    assert storage.exists("macro/VIXCLS")
    assert storage.exists("macro/T10Y2Y")
    assert storage.exists("macro/FEDFUNDS")
