"""Momentum Composite calculation: 5 components, z-scored, weighted sum.

Components (XAU/USD, no volume):
  - Momentum (6M return, skip last month): 44%
  - Trend (price vs 50/200 DMA): 22%
  - RSI (distance from extremes): 17%
  - ATR volatility (percentile rank): 11%
  - Support/Resistance (price clustering): 6%

Signal classification:
  STRONG_BUY  = composite > 2.0σ
  BUY         = composite > 1.5σ
  NEUTRAL     = between -1.5σ and 1.5σ
  SELL        = composite < -1.5σ
  STRONG_SELL = composite < -2.0σ
"""

from enum import Enum

import pandas as pd


class Signal(Enum):
    """Momentum composite signal classification."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


def rolling_zscore(series: pd.Series, window: int = 252) -> pd.Series:
    """Compute rolling z-score of a series.

    Formula: ``(x - rolling_mean(x, window)) / rolling_std(x, window)``.
    Uses sample standard deviation (ddof=1, pandas default).

    When standard deviation is zero (constant values in window), returns NaN
    for that position (not inf).

    Args:
        series: Input data series.
        window: Rolling window size (default 252 trading days).

    Returns:
        Z-score series. First ``window - 1`` values are NaN.

    Raises:
        ValueError: If ``window < 2`` (need at least 2 values for std).
    """
    if window < 2:
        raise ValueError(f"window must be >= 2, got {window}")
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    return (series - rolling_mean) / rolling_std
