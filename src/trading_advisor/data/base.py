"""Abstract DataProvider base class.

Implemented in Task 1A.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataProvider(ABC):
    """Abstract base class for all data providers."""

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol between start and end dates.

        Args:
            symbol: Ticker symbol, e.g. 'XAUUSD'.
            start: Start date in 'YYYY-MM-DD' format.
            end: End date in 'YYYY-MM-DD' format.

        Returns:
            DataFrame with columns: date, open, high, low, close, volume.
        """
        ...
