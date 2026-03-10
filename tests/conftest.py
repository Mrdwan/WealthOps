"""Shared pytest fixtures for WealthOps tests."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture()
def sample_ohlcv() -> pd.DataFrame:
    """Minimal OHLCV DataFrame for unit tests (10 rows)."""
    data = {
        "date": pd.date_range("2024-01-01", periods=10, freq="B"),
        "open": [2000.0 + i for i in range(10)],
        "high": [2010.0 + i for i in range(10)],
        "low": [1990.0 + i for i in range(10)],
        "close": [2005.0 + i for i in range(10)],
        "volume": [0.0] * 10,  # Volume excluded for XAU/USD
    }
    df = pd.DataFrame(data).set_index("date")
    return df
