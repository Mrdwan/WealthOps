"""FRED API data provider — VIX, T10Y2Y, FEDFUNDS macro data.

Implemented in Task 1A.
"""

from __future__ import annotations

import pandas as pd

from trading_advisor.data.base import DataProvider


class FredProvider(DataProvider):
    """Fetches macro data series from the FRED API."""

    def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raise NotImplementedError("FredProvider.fetch_ohlcv — Task 1A")
