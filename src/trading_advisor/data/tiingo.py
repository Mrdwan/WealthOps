"""Tiingo API data provider — XAU/USD and DXY daily OHLCV.

Implemented in Task 1A.
"""

from __future__ import annotations

import pandas as pd

from trading_advisor.data.base import DataProvider


class TiingoProvider(DataProvider):
    """Fetches daily OHLCV from the Tiingo Forex API."""

    def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        raise NotImplementedError("TiingoProvider.fetch_ohlcv — Task 1A")
