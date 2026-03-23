"""Technical indicator calculations: RSI, EMA, ADX, ATR, MACD, wick ratios.

All functions take a pandas Series (or DataFrame with OHLCV columns) and
return a Series or the DataFrame with new columns appended.
"""

import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI using Wilder's smoothing method.

    Args:
        close: Series of closing prices.
        period: Lookback period (default 14).

    Returns:
        Series of RSI values. First ``period`` values are NaN (warmup).
    """
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)

    result = pd.Series(np.nan, index=close.index, dtype=np.float64)

    # Initial averages: simple mean of first `period` gain/loss values
    # (indices 1 through period inclusive, since index 0 is NaN from diff)
    avg_gain: np.float64 = np.float64(gains.iloc[1 : period + 1].mean())
    avg_loss: np.float64 = np.float64(losses.iloc[1 : period + 1].mean())

    # Place the first RSI value at index `period`.
    # numpy float64 division: x/0 → inf, 0/0 → nan (IEEE 754)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        result.iloc[period] = 100.0 - 100.0 / (1.0 + rs)

    # Subsequent values use Wilder's smoothing
    for i in range(period + 1, len(close)):
        current_gain = np.float64(gains.iloc[i])
        current_loss = np.float64(losses.iloc[i])
        avg_gain = (avg_gain * np.float64(period - 1) + current_gain) / np.float64(period)
        avg_loss = (avg_loss * np.float64(period - 1) + current_loss) / np.float64(period)
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = avg_gain / avg_loss
            result.iloc[i] = 100.0 - 100.0 / (1.0 + rs)

    return result
