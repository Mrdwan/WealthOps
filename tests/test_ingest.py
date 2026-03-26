"""Tests for the DataIngestor class in trading_advisor.data.ingest."""

from pathlib import Path

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


def test_fresh_ohlcv_ingest_writes_and_returns_valid(tmp_path: Path) -> None:
    """Fresh ingest writes data and returns a valid ValidationResult."""
    storage = LocalStorage(tmp_path)
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


def test_incremental_ohlcv_ingest_appends_new_data(tmp_path: Path) -> None:
    """Incremental ingest only fetches dates after the last stored date."""
    storage = LocalStorage(tmp_path)
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


def test_invalid_ohlcv_raises_and_does_not_write(tmp_path: Path) -> None:
    """Invalid OHLCV data raises ValueError and does not write to storage."""
    storage = LocalStorage(tmp_path)
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


def test_valid_ohlcv_with_warnings_still_writes(tmp_path: Path) -> None:
    """Valid OHLCV data with warnings still writes (valid=True with non-empty warnings)."""
    storage = LocalStorage(tmp_path)
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


def test_already_up_to_date_returns_valid_without_fetch(tmp_path: Path) -> None:
    """When stored data covers up to end date, returns valid without fetching."""
    storage = LocalStorage(tmp_path)
    existing = _make_ohlcv("2024-01-01", 5)
    last_date = existing.index[-1]
    end_date = (last_date - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    storage.write_parquet("ohlcv/XAUUSD", existing)

    fetch_call_count = 0

    class CountingOHLCVProvider(OHLCVProvider):
        def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
            nonlocal fetch_call_count
            fetch_call_count += 1
            return existing

    ingestor = DataIngestor(
        ohlcv_provider=CountingOHLCVProvider(),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", end_date, "ohlcv/XAUUSD")

    assert result.valid is True
    assert result.errors == []
    # Provider must NOT be called when data is already up to date
    assert fetch_call_count == 0


def test_empty_fetch_returns_valid_without_writing(tmp_path: Path) -> None:
    """Empty fetch result returns valid ValidationResult without writing."""
    storage = LocalStorage(tmp_path)
    empty_data: pd.DataFrame = pd.DataFrame()

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(empty_data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-01-31", "ohlcv/XAUUSD")

    assert result.valid is True
    assert not storage.exists("ohlcv/XAUUSD")


def test_ohlcv_dedup_overlapping_dates_keeps_last(tmp_path: Path) -> None:
    """Overlapping dates between existing and new data are deduplicated (keep last)."""
    storage = LocalStorage(tmp_path)
    existing = _make_ohlcv("2024-01-01", 5)
    # New data overlaps the last 2 rows of existing
    overlap_start = existing.index[-2].strftime("%Y-%m-%d")
    new_data = _make_ohlcv(overlap_start, 4)
    # Shift all OHLC values up so the data stays valid but is distinguishable
    new_data["open"] = new_data["open"] + 999.0
    new_data["high"] = new_data["high"] + 999.0
    new_data["low"] = new_data["low"] + 999.0
    new_data["close"] = new_data["close"] + 999.0

    # Provider that always returns new_data ignoring date filters, so that
    # overlapping rows are present in the fetched result.
    class OverlapOHLCVProvider(OHLCVProvider):
        def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
            return new_data.copy()

    # Existing is already in storage; provider returns new_data (which overlaps)
    storage.write_parquet("ohlcv/XAUUSD", existing)

    ingestor = DataIngestor(
        ohlcv_provider=OverlapOHLCVProvider(),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    result = ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-12-31", "ohlcv/XAUUSD")
    assert result.valid is True

    stored = storage.read_parquet("ohlcv/XAUUSD")
    assert stored.index.duplicated().sum() == 0
    assert stored.index.is_monotonic_increasing
    # Overlapping rows must have the NEW (shifted) values, not the old ones
    overlap_idx = new_data.index[new_data.index.isin(existing.index)]
    for ts in overlap_idx:
        assert stored.loc[ts, "close"] == pytest.approx(new_data.loc[ts, "close"])


def test_combined_data_validation_failure_raises_and_does_not_write(
    tmp_path: Path,
) -> None:
    """When combined (existing + new) data fails validation, raises ValueError without writing."""
    storage = LocalStorage(tmp_path)
    # Write corrupted existing data directly (bypassing ingestor validation)
    idx = pd.date_range("2024-01-01", periods=3, freq="B", name="date")
    corrupt_existing = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [80.0, 80.0, 80.0],  # high < low — invalid
            "low": [95.0, 95.0, 95.0],
            "close": [90.0, 90.0, 90.0],
        },
        index=idx,
    )
    storage.write_parquet("ohlcv/XAUUSD", corrupt_existing)

    # New data is valid on its own
    new_data = _make_ohlcv("2024-01-08", 3)

    ingestor = DataIngestor(
        ohlcv_provider=FakeOHLCVProvider(new_data),
        macro_provider=FakeMacroProvider(_make_macro("2024-01-01", 0)),
        storage=storage,
    )

    with pytest.raises(ValueError):
        ingestor.ingest_ohlcv("XAUUSD", "2024-01-01", "2024-01-31", "ohlcv/XAUUSD")

    # Storage must still contain only the corrupted existing data (not updated)
    stored = storage.read_parquet("ohlcv/XAUUSD")
    assert len(stored) == len(corrupt_existing)


# ---------------------------------------------------------------------------
# Tests: ingest_macro
# ---------------------------------------------------------------------------


def test_fresh_macro_ingest_writes_data(tmp_path: Path) -> None:
    """Fresh macro ingest writes data to storage."""
    storage = LocalStorage(tmp_path)
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


def test_incremental_macro_ingest_appends_new_data(tmp_path: Path) -> None:
    """Incremental macro ingest appends new data after existing."""
    storage = LocalStorage(tmp_path)
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


def test_macro_already_up_to_date_returns_early(tmp_path: Path) -> None:
    """When stored macro data covers end date, returns without fetching."""
    storage = LocalStorage(tmp_path)
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


def test_macro_empty_fetch_returns_early(tmp_path: Path) -> None:
    """Empty macro fetch returns without writing."""
    storage = LocalStorage(tmp_path)
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
    tmp_path: Path,
) -> None:
    """run_daily_ingest ingests 5 series and returns 2 OHLCV validation results."""
    storage = LocalStorage(tmp_path)
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


def test_run_daily_ingest_uses_custom_start_date(tmp_path: Path) -> None:
    """run_daily_ingest passes start_date override to providers."""
    storage = LocalStorage(tmp_path)
    ohlcv_data = _make_ohlcv("2015-01-01", 5)
    macro_data = _make_macro("2015-01-01", 5)

    recorded_starts: list[str] = []

    class RecordingOHLCVProvider(FakeOHLCVProvider):
        """Wraps FakeOHLCVProvider to record the start arg."""

        def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
            recorded_starts.append(start)
            return super().fetch_ohlcv(symbol, start, end)

    ingestor = DataIngestor(
        ohlcv_provider=RecordingOHLCVProvider(ohlcv_data),
        macro_provider=FakeMacroProvider(macro_data),
        storage=storage,
    )

    results = ingestor.run_daily_ingest("2024-12-31", start_date="2015-01-01")

    assert results["XAUUSD"].valid is True
    assert all(s == "2015-01-01" for s in recorded_starts)
