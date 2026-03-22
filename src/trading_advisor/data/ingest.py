"""Data ingest pipeline — orchestrates OHLCV and macro data fetching and storage."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from trading_advisor.data.base import MacroProvider, OHLCVProvider
from trading_advisor.data.validation import ValidationResult, validate_ohlcv
from trading_advisor.storage.base import StorageBackend

_DEFAULT_START: str = "2015-01-01"


class DataIngestor:
    """Orchestrates fetching, validating, and persisting market and macro data.

    Supports incremental updates: if data already exists in storage, only the
    missing date range is fetched and appended.

    Args:
        ohlcv_provider: Provider for OHLCV market data.
        macro_provider: Provider for macro time-series data.
        storage: Backend used to read and write persisted DataFrames.
        validator: Callable that validates an OHLCV DataFrame. Defaults to
            :func:`~trading_advisor.data.validation.validate_ohlcv`.
    """

    def __init__(
        self,
        ohlcv_provider: OHLCVProvider,
        macro_provider: MacroProvider,
        storage: StorageBackend,
        validator: Callable[[pd.DataFrame], ValidationResult] = validate_ohlcv,
    ) -> None:
        self._ohlcv_provider = ohlcv_provider
        self._macro_provider = macro_provider
        self._storage = storage
        self._validator = validator

    def ingest_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        storage_key: str,
    ) -> ValidationResult:
        """Fetch, validate, and store OHLCV data for a symbol.

        If data already exists for *storage_key*, only dates after the last
        stored date are fetched and appended.

        Args:
            symbol: Ticker symbol, e.g. ``'XAUUSD'``.
            start: Start date in ``'YYYY-MM-DD'`` format.
            end: End date in ``'YYYY-MM-DD'`` format.
            storage_key: Key under which to read/write data in the storage
                backend.

        Returns:
            :class:`~trading_advisor.data.validation.ValidationResult` for the
            newly fetched data. Returns a trivially valid result when no new
            data needs to be fetched or when the fetch returns empty.

        Raises:
            ValueError: If the fetched data fails validation. No data is
                written in this case.
        """
        existing: pd.DataFrame | None = None
        effective_start = start

        if self._storage.exists(storage_key):
            existing = self._storage.read_parquet(storage_key)
            last_date = pd.Timestamp(existing.index.max())
            effective_start = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        if pd.Timestamp(effective_start) > pd.Timestamp(end):
            return ValidationResult(valid=True, errors=[], warnings=[])

        new_data = self._ohlcv_provider.fetch_ohlcv(symbol, effective_start, end)

        if new_data.empty:
            return ValidationResult(valid=True, errors=[], warnings=[])

        result = self._validator(new_data)

        if not result.valid:
            raise ValueError(f"OHLCV validation failed for {symbol!r}: {result.errors}")

        if existing is not None:
            combined = pd.concat([existing, new_data])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
            combined_result = self._validator(combined)
            if not combined_result.valid:
                raise ValueError(
                    f"Combined OHLCV validation failed for {symbol!r}: {combined_result.errors}"
                )
            self._storage.write_parquet(storage_key, combined)
        else:
            self._storage.write_parquet(storage_key, new_data)

        return result

    def ingest_macro(
        self,
        series_id: str,
        start: str,
        end: str,
        storage_key: str,
    ) -> None:
        """Fetch and store a macro data series.

        If data already exists for *storage_key*, only dates after the last
        stored date are fetched and appended.

        Args:
            series_id: FRED series identifier, e.g. ``'VIXCLS'``.
            start: Start date in ``'YYYY-MM-DD'`` format.
            end: End date in ``'YYYY-MM-DD'`` format.
            storage_key: Key under which to read/write data in the storage
                backend.
        """
        existing: pd.DataFrame | None = None
        effective_start = start

        if self._storage.exists(storage_key):
            existing = self._storage.read_parquet(storage_key)
            last_date = pd.Timestamp(existing.index.max())
            effective_start = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        if pd.Timestamp(effective_start) > pd.Timestamp(end):
            return

        new_data = self._macro_provider.fetch_series(series_id, effective_start, end)

        if new_data.empty:
            return

        if existing is not None:
            combined = pd.concat([existing, new_data])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined = combined.sort_index()
            self._storage.write_parquet(storage_key, combined)
        else:
            self._storage.write_parquet(storage_key, new_data)

    def run_daily_ingest(self, end_date: str) -> dict[str, ValidationResult]:
        """Run the full daily ingest for all configured symbols and macro series.

        Ingests XAUUSD and EURUSD OHLCV data, plus VIX, T10Y2Y, and FEDFUNDS
        macro series, all starting from :data:`_DEFAULT_START` (``2015-01-01``).

        Args:
            end_date: End date in ``'YYYY-MM-DD'`` format.

        Returns:
            Dictionary mapping OHLCV symbol name to its
            :class:`~trading_advisor.data.validation.ValidationResult`. Keys
            are ``'XAUUSD'`` and ``'EURUSD'``.
        """
        start = _DEFAULT_START

        xau_result = self.ingest_ohlcv("XAUUSD", start, end_date, "ohlcv/XAUUSD_daily")
        eur_result = self.ingest_ohlcv("EURUSD", start, end_date, "ohlcv/EURUSD_daily")

        self.ingest_macro("VIXCLS", start, end_date, "macro/VIXCLS")
        self.ingest_macro("T10Y2Y", start, end_date, "macro/T10Y2Y")
        self.ingest_macro("FEDFUNDS", start, end_date, "macro/FEDFUNDS")

        return {"XAUUSD": xau_result, "EURUSD": eur_result}
