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

import numpy as np
import numpy.typing as npt
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


def momentum_component(close: pd.Series, window: int = 252) -> pd.Series:
    """Compute momentum composite component (weight: 44%).

    Raw: 6-month return skipping most recent month.
    ``momentum_raw = close[t-21] / close[t-126] - 1``

    Args:
        close: Closing price series.
        window: Rolling z-score window (default 252).

    Returns:
        Z-scored momentum series.
    """
    momentum_raw = close.shift(21) / close.shift(126) - 1
    return rolling_zscore(momentum_raw, window=window)


def trend_component(
    close: pd.Series,
    sma_50: pd.Series,
    sma_200: pd.Series,
    window: int = 252,
) -> pd.Series:
    """Compute trend confirmation composite component (weight: 22%).

    Raw: sum of 3 binary conditions (0 to 3).
    ``trend_raw = (close > SMA_50) + (close > SMA_200) + (SMA_50 > SMA_200)``

    Args:
        close: Closing price series.
        sma_50: 50-day simple moving average.
        sma_200: 200-day simple moving average.
        window: Rolling z-score window (default 252).

    Returns:
        Z-scored trend series.
    """
    trend_raw = (
        (close > sma_50).astype(np.float64)
        + (close > sma_200).astype(np.float64)
        + (sma_50 > sma_200).astype(np.float64)
    )
    return rolling_zscore(trend_raw, window=window)


def rsi_filter_component(rsi: pd.Series, window: int = 252) -> pd.Series:
    """Compute RSI filter composite component (weight: 17%).

    Raw: distance from RSI extremes. Maximum at RSI=50.
    ``rsi_raw = 50 - abs(RSI_14 - 50)``

    Args:
        rsi: RSI(14) series.
        window: Rolling z-score window (default 252).

    Returns:
        Z-scored RSI filter series.
    """
    rsi_raw = 50.0 - (rsi - 50.0).abs()
    return rolling_zscore(rsi_raw, window=window)


def _rolling_percentile_rank(x: npt.NDArray[np.float64]) -> float:
    """Percentile rank of the last value within its window (0-100).

    Args:
        x: Array of values in the rolling window.

    Returns:
        Percentile rank (0-100) of the last element.
    """
    current: float = float(x[-1])
    below: int = int(np.sum(x[:-1] < current))
    return float(below) / (len(x) - 1) * 100.0


def atr_volatility_component(atr: pd.Series, window: int = 252) -> pd.Series:
    """Compute ATR volatility composite component (weight: 11%).

    Raw: penalizes volatility extremes. Maximum at 50th percentile.
    ``atr_percentile = percentile_rank(ATR, window)``  (0 to 100)
    ``atr_raw = 1 - abs(atr_percentile - 50) / 50``   (0.0 to 1.0)

    Args:
        atr: ATR(14) series.
        window: Rolling window for both percentile rank and z-score (default 252).

    Returns:
        Z-scored ATR volatility series.
    """
    atr_percentile = atr.rolling(window=window).apply(_rolling_percentile_rank, raw=True)
    atr_raw = 1.0 - np.abs(atr_percentile - 50.0) / 50.0
    return rolling_zscore(atr_raw, window=window)


def sr_proximity_component(
    close: pd.Series,
    high: pd.Series,
    lookback: int = 20,
    window: int = 252,
) -> pd.Series:
    """Compute support/resistance proximity component (weight: 6%).

    Raw: proximity to 20-day high. Higher = closer to breakout territory.
    ``sr_raw = 1 - (high_20d - close) / close``

    Args:
        close: Closing price series.
        high: High price series.
        lookback: Rolling high lookback period (default 20).
        window: Rolling z-score window (default 252).

    Returns:
        Z-scored S/R proximity series.
    """
    high_nd = high.rolling(window=lookback).max()
    sr_raw = 1.0 - (high_nd - close) / close
    return rolling_zscore(sr_raw, window=window)
