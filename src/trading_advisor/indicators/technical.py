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


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Compute Exponential Moving Average.

    Uses pandas ewm with ``adjust=False`` (recursive formula).
    Multiplier = 2 / (span + 1). EMA[0] = series[0].

    Args:
        series: Input price series.
        span: EMA period (e.g., 8, 20, 50).

    Returns:
        EMA series. All values are valid (no NaN warmup).

    Raises:
        ValueError: If span is less than 1.
    """
    if span < 1:
        raise ValueError(f"span must be >= 1, got {span}")
    return series.ewm(span=span, adjust=False).mean()


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """Compute Simple Moving Average.

    Args:
        series: Input price series.
        window: Rolling window size (e.g., 50, 200).

    Returns:
        SMA series. First ``window - 1`` values are NaN.

    Raises:
        ValueError: If window is less than 1.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    return series.rolling(window=window).mean()


def compute_macd_histogram(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.Series:
    """Compute MACD histogram (MACD line minus signal line).

    MACD line = EMA(fast) - EMA(slow).
    Signal line = EMA(signal) of MACD line.
    Histogram = MACD line - Signal line.

    Args:
        close: Series of closing prices.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal line EMA period (default 9).

    Returns:
        MACD histogram series. No NaN values (EMA starts from first value).

    Raises:
        ValueError: If fast, slow, or signal is less than 1, or if fast >= slow.
    """
    if fast < 1:
        raise ValueError(f"fast must be >= 1, got {fast}")
    if slow < 1:
        raise ValueError(f"slow must be >= 1, got {slow}")
    if signal < 1:
        raise ValueError(f"signal must be >= 1, got {signal}")
    if fast >= slow:
        raise ValueError(f"fast must be < slow, got fast={fast}, slow={slow}")

    ema_fast = compute_ema(close, span=fast)
    ema_slow = compute_ema(close, span=slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, span=signal)
    return macd_line - signal_line


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.DataFrame:
    """Compute Average Directional Index with +DI and -DI.

    Uses Wilder's smoothing for directional movement and ADX.

    Args:
        high: Series of high prices.
        low: Series of low prices.
        close: Series of closing prices.
        period: ADX period (default 14).

    Returns:
        DataFrame with columns ``plus_di``, ``minus_di``, ``adx``.
        First ``period`` rows have NaN for DI columns.
        First ``2 * period - 1`` rows have NaN for ADX column.

    Raises:
        ValueError: If period is less than 2.
    """
    if period < 2:
        raise ValueError(f"period must be >= 2, got {period}")

    n = len(high)
    plus_dm = np.full(n, np.nan, dtype=np.float64)
    minus_dm = np.full(n, np.nan, dtype=np.float64)
    tr = np.full(n, np.nan, dtype=np.float64)

    # Step 1: Raw +DM, -DM, TR
    for i in range(1, n):
        up_move = float(high.iloc[i]) - float(high.iloc[i - 1])
        down_move = float(low.iloc[i - 1]) - float(low.iloc[i])

        if up_move > 0.0 and up_move > down_move:
            plus_dm[i] = up_move
        else:
            plus_dm[i] = 0.0

        if down_move > 0.0 and down_move > up_move:
            minus_dm[i] = down_move
        else:
            minus_dm[i] = 0.0

        tr[i] = max(
            float(high.iloc[i]) - float(low.iloc[i]),
            abs(float(high.iloc[i]) - float(close.iloc[i - 1])),
            abs(float(low.iloc[i]) - float(close.iloc[i - 1])),
        )

    # Step 2: Wilder's smoothing of +DM, -DM, TR
    s_plus_dm = np.full(n, np.nan, dtype=np.float64)
    s_minus_dm = np.full(n, np.nan, dtype=np.float64)
    s_tr = np.full(n, np.nan, dtype=np.float64)

    # First smoothed value at index `period`: sum of indices 1..period
    s_plus_dm[period] = np.sum(plus_dm[1 : period + 1])
    s_minus_dm[period] = np.sum(minus_dm[1 : period + 1])
    s_tr[period] = np.sum(tr[1 : period + 1])

    for i in range(period + 1, n):
        decay = np.float64(period - 1) / np.float64(period)
        s_plus_dm[i] = s_plus_dm[i - 1] * decay + plus_dm[i]
        s_minus_dm[i] = s_minus_dm[i - 1] * decay + minus_dm[i]
        s_tr[i] = s_tr[i - 1] * decay + tr[i]

    # Step 3 & 4: DI and DX
    plus_di = np.full(n, np.nan, dtype=np.float64)
    minus_di = np.full(n, np.nan, dtype=np.float64)
    dx = np.full(n, np.nan, dtype=np.float64)

    with np.errstate(divide="ignore", invalid="ignore"):
        for i in range(period, n):
            if s_tr[i] == 0.0:
                plus_di[i] = 0.0
                minus_di[i] = 0.0
            else:
                plus_di[i] = 100.0 * s_plus_dm[i] / s_tr[i]
                minus_di[i] = 100.0 * s_minus_dm[i] / s_tr[i]

            di_sum = plus_di[i] + minus_di[i]
            if di_sum == 0.0:
                dx[i] = 0.0
            else:
                dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum

    # Step 5: ADX
    adx = np.full(n, np.nan, dtype=np.float64)
    first_adx_idx = 2 * period - 1

    if first_adx_idx < n:
        # First ADX: mean of DX[period .. 2*period-1]
        adx[first_adx_idx] = np.mean(dx[period : first_adx_idx + 1])

        for i in range(first_adx_idx + 1, n):
            adx[i] = (adx[i - 1] * np.float64(period - 1) + dx[i]) / np.float64(period)

    return pd.DataFrame(
        {"plus_di": plus_di, "minus_di": minus_di, "adx": adx},
        index=high.index,
    )


def compute_ema_fan(ema_8: pd.Series, ema_20: pd.Series, ema_50: pd.Series) -> pd.Series:
    """Check if EMAs are in bullish fan alignment.

    Bullish fan: EMA_8 > EMA_20 > EMA_50 (short-term leads).

    Args:
        ema_8: 8-period EMA.
        ema_20: 20-period EMA.
        ema_50: 50-period EMA.

    Returns:
        Boolean Series: True when EMA_8 > EMA_20 > EMA_50.
    """
    return (ema_8 > ema_20) & (ema_20 > ema_50)
