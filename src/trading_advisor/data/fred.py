"""FRED API data provider — VIX, T10Y2Y, FEDFUNDS macro data."""

from __future__ import annotations

import pandas as pd
from fredapi import Fred

from trading_advisor.data.base import MacroProvider


class FredProvider(MacroProvider):
    """Fetches macro data series from the FRED API.

    Args:
        api_key: FRED API key used to authenticate requests.
        fred_client: Optional pre-constructed ``fredapi.Fred`` instance.
            If ``None``, a new instance is created using ``api_key``.
            Provide a mock here for testing to avoid real network calls.
    """

    def __init__(self, api_key: str, fred_client: Fred | None = None) -> None:
        """Initialise FredProvider.

        Args:
            api_key: FRED API key.
            fred_client: Optional ``fredapi.Fred`` instance for dependency
                injection; created automatically when ``None``.
        """
        self._fred: Fred = fred_client if fred_client is not None else Fred(api_key=api_key)

    def fetch_series(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        """Fetch a macro data series from FRED between start and end dates.

        Args:
            series_id: FRED series identifier, e.g. ``'VIXCLS'``,
                ``'T10Y2Y'``, or ``'FEDFUNDS'``.
            start: Start date in ``'YYYY-MM-DD'`` format.
            end: End date in ``'YYYY-MM-DD'`` format.

        Returns:
            DataFrame with a DatetimeIndex named ``date`` and a single
            ``value`` column. Rows with NaN values are dropped. Returns
            an empty DataFrame (correct schema) if no valid data exists.

        Raises:
            RuntimeError: If the FRED API call fails for any reason.
        """
        try:
            raw: pd.Series = self._fred.get_series(
                series_id,
                observation_start=start,
                observation_end=end,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch FRED series '{series_id}': {exc}") from exc

        df = raw.to_frame(name="value")
        df.index.name = "date"
        df = df.dropna()
        df = df.sort_index()

        if df.empty:
            empty_index = pd.DatetimeIndex([], name="date")
            return pd.DataFrame({"value": pd.Series([], dtype=float)}, index=empty_index)

        return df
