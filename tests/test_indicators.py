"""Tests for technical indicators."""

import numpy as np
import pandas as pd
import pytest

from trading_advisor.indicators.technical import (
    compute_adx,
    compute_atr,
    compute_distance_from_20d_low,
    compute_ema,
    compute_ema_fan,
    compute_macd_histogram,
    compute_relative_strength_vs_usd,
    compute_rsi,
    compute_sma,
    compute_wick_ratios,
)


class TestComputeRsi:
    """Tests for compute_rsi (Wilder's RSI)."""

    def test_known_values_period_3(self) -> None:
        """Verify RSI values match hand-computed Wilder's smoothing for period=3."""
        close = pd.Series([10.0, 11.0, 12.0, 11.0, 12.0, 13.0, 14.0], dtype=np.float64)
        result = compute_rsi(close, period=3)

        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert pd.isna(result.iloc[2])
        assert result.iloc[3] == pytest.approx(200.0 / 3.0, abs=1e-4)
        assert result.iloc[4] == pytest.approx(700.0 / 9.0, abs=1e-4)
        assert result.iloc[5] == pytest.approx(2300.0 / 27.0, abs=1e-4)
        assert result.iloc[6] == pytest.approx(7300.0 / 81.0, abs=1e-4)

    def test_all_gains_rsi_100(self) -> None:
        """All positive changes → avg_loss = 0 → RS = inf → RSI = 100."""
        close = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0], dtype=np.float64)
        result = compute_rsi(close, period=3)

        assert result.iloc[3] == pytest.approx(100.0, abs=1e-4)
        assert result.iloc[4] == pytest.approx(100.0, abs=1e-4)

    def test_all_losses_rsi_0(self) -> None:
        """All negative changes → avg_gain = 0 → RS = 0 → RSI = 0."""
        close = pd.Series([14.0, 13.0, 12.0, 11.0, 10.0], dtype=np.float64)
        result = compute_rsi(close, period=3)

        assert result.iloc[3] == pytest.approx(0.0, abs=1e-4)
        assert result.iloc[4] == pytest.approx(0.0, abs=1e-4)

    def test_warmup_nan(self) -> None:
        """First ``period`` values (indices 0 through period-1) must be NaN."""
        close = pd.Series(
            [float(i) for i in range(30)],
            dtype=np.float64,
        )
        result = compute_rsi(close, period=14)

        for i in range(14):
            assert pd.isna(result.iloc[i]), f"Expected NaN at index {i}"

    def test_default_period_14(self) -> None:
        """Default period is 14: first 14 values NaN, index 14 is a valid float."""
        close = pd.Series(
            [float(i) for i in range(30)],
            dtype=np.float64,
        )
        result = compute_rsi(close)

        for i in range(14):
            assert pd.isna(result.iloc[i]), f"Expected NaN at index {i}"
        assert not pd.isna(result.iloc[14])
        assert isinstance(result.iloc[14], float)


class TestComputeEma:
    """Tests for compute_ema (exponential moving average)."""

    def test_known_values_span_3(self) -> None:
        """Verify EMA values match hand-computed recursive formula for span=3."""
        close = pd.Series([10.0, 11.0, 12.0, 11.0, 13.0, 14.0], dtype=np.float64)
        result = compute_ema(close, span=3)

        assert result.iloc[0] == pytest.approx(10.0, abs=1e-6)
        assert result.iloc[1] == pytest.approx(10.5, abs=1e-6)
        assert result.iloc[2] == pytest.approx(11.25, abs=1e-6)
        assert result.iloc[3] == pytest.approx(11.125, abs=1e-6)
        assert result.iloc[4] == pytest.approx(12.0625, abs=1e-6)
        assert result.iloc[5] == pytest.approx(13.03125, abs=1e-6)

    def test_no_nan_warmup(self) -> None:
        """EMA must have no NaN values — all values valid from index 0."""
        close = pd.Series([float(i + 1) for i in range(10)], dtype=np.float64)
        result = compute_ema(close, span=5)

        for i in range(len(result)):
            assert not pd.isna(result.iloc[i]), f"Unexpected NaN at index {i}"

    def test_invalid_span_raises(self) -> None:
        close = pd.Series([1.0, 2.0, 3.0], dtype=np.float64)
        with pytest.raises(ValueError, match="span must be >= 1"):
            compute_ema(close, span=0)


class TestComputeSma:
    """Tests for compute_sma (simple moving average)."""

    def test_known_values_window_3(self) -> None:
        """Verify SMA values match hand-computed rolling mean for window=3."""
        close = pd.Series([10.0, 11.0, 12.0, 11.0, 13.0, 14.0], dtype=np.float64)
        result = compute_sma(close, window=3)

        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(11.0, abs=1e-6)
        assert result.iloc[3] == pytest.approx(11.333333, abs=1e-5)
        assert result.iloc[4] == pytest.approx(12.0, abs=1e-6)
        assert result.iloc[5] == pytest.approx(12.666667, abs=1e-5)

    def test_warmup_nan(self) -> None:
        """First window-1 values must be NaN."""
        close = pd.Series([float(i + 1) for i in range(10)], dtype=np.float64)
        result = compute_sma(close, window=5)

        for i in range(4):
            assert pd.isna(result.iloc[i]), f"Expected NaN at index {i}"
        assert not pd.isna(result.iloc[4])

    def test_invalid_window_raises(self) -> None:
        close = pd.Series([1.0, 2.0, 3.0], dtype=np.float64)
        with pytest.raises(ValueError, match="window must be >= 1"):
            compute_sma(close, window=0)


class TestComputeEmaFan:
    """Tests for compute_ema_fan (bullish EMA fan alignment check)."""

    def test_all_aligned(self) -> None:
        """EMA_8 > EMA_20 > EMA_50 at every bar → all True."""
        ema_8 = pd.Series([100.0, 101.0, 102.0], dtype=np.float64)
        ema_20 = pd.Series([99.0, 100.0, 101.0], dtype=np.float64)
        ema_50 = pd.Series([98.0, 99.0, 100.0], dtype=np.float64)
        result = compute_ema_fan(ema_8, ema_20, ema_50)

        assert list(result) == [True, True, True]

    def test_not_aligned(self) -> None:
        """EMA_8 < EMA_20 at every bar → all False."""
        ema_8 = pd.Series([100.0, 99.0, 98.0], dtype=np.float64)
        ema_20 = pd.Series([101.0, 100.0, 99.0], dtype=np.float64)
        ema_50 = pd.Series([98.0, 99.0, 100.0], dtype=np.float64)
        result = compute_ema_fan(ema_8, ema_20, ema_50)

        assert list(result) == [False, False, False]

    def test_mixed(self) -> None:
        """Mixed alignment: True, True, False per index."""
        ema_8 = pd.Series([100.0, 101.0, 99.0], dtype=np.float64)
        ema_20 = pd.Series([99.0, 100.0, 100.0], dtype=np.float64)
        ema_50 = pd.Series([98.0, 99.0, 101.0], dtype=np.float64)
        result = compute_ema_fan(ema_8, ema_20, ema_50)

        assert list(result) == [True, True, False]

    def test_returns_bool_dtype(self) -> None:
        """Return dtype must be bool."""
        ema_8 = pd.Series([100.0, 101.0], dtype=np.float64)
        ema_20 = pd.Series([99.0, 100.0], dtype=np.float64)
        ema_50 = pd.Series([98.0, 99.0], dtype=np.float64)
        result = compute_ema_fan(ema_8, ema_20, ema_50)

        assert result.dtype == bool

    def test_second_condition_decides(self) -> None:
        """Fan is False when EMA_20 < EMA_50 even if EMA_8 > EMA_20."""
        ema_8 = pd.Series([100.0, 105.0], dtype=np.float64)
        ema_20 = pd.Series([99.0, 100.0], dtype=np.float64)
        ema_50 = pd.Series([101.0, 103.0], dtype=np.float64)
        result = compute_ema_fan(ema_8, ema_20, ema_50)
        expected = pd.Series([False, False])
        pd.testing.assert_series_equal(result, expected)

    def test_equality_is_not_fan(self) -> None:
        """Equality does not satisfy strict greater-than for fan."""
        ema_8 = pd.Series([100.0, 100.0], dtype=np.float64)
        ema_20 = pd.Series([100.0, 99.0], dtype=np.float64)
        ema_50 = pd.Series([99.0, 99.0], dtype=np.float64)
        result = compute_ema_fan(ema_8, ema_20, ema_50)
        # Index 0: ema_8 == ema_20 → False (not strictly greater)
        # Index 1: ema_20 == ema_50 → False (not strictly greater)
        expected = pd.Series([False, False])
        pd.testing.assert_series_equal(result, expected)


class TestComputeMacdHistogram:
    """Tests for compute_macd_histogram."""

    def test_known_values(self) -> None:
        """Verify MACD histogram values match hand-computed results for fast=2, slow=3, signal=2."""
        close = pd.Series([10.0, 12.0, 11.0, 13.0, 14.0], dtype=np.float64)
        result = compute_macd_histogram(close, fast=2, slow=3, signal=2)

        # Histogram = MACD - Signal, pre-computed exact fractions:
        # [0.0, 1/9, -1/27, 2/27, 13/243]
        expected = [0.0, 1 / 9, -1 / 27, 2 / 27, 13 / 243]
        for i, exp in enumerate(expected):
            assert result.iloc[i] == pytest.approx(
                exp, abs=1e-4
            ), f"Mismatch at index {i}: got {result.iloc[i]}, expected {exp}"

    def test_constant_prices_zero(self) -> None:
        """All EMAs equal constant price → MACD = 0, Signal = 0, Histogram = 0."""
        close = pd.Series([100.0] * 20, dtype=np.float64)
        result = compute_macd_histogram(close)

        for i in range(len(result)):
            assert result.iloc[i] == pytest.approx(
                0.0
            ), f"Expected 0.0 at index {i}, got {result.iloc[i]}"

    def test_uptrend_positive(self) -> None:
        """In a sustained uptrend the histogram should be positive at the last bar."""
        close = pd.Series([100.0 + i for i in range(30)], dtype=np.float64)
        result = compute_macd_histogram(close)

        assert result.iloc[-1] > 0

    def test_fast_gte_slow_raises(self) -> None:
        """fast >= slow must raise ValueError."""
        close = pd.Series([1.0, 2.0, 3.0], dtype=np.float64)
        with pytest.raises(ValueError, match="fast.*slow"):
            compute_macd_histogram(close, fast=5, slow=3)

    def test_invalid_period_raises(self) -> None:
        """fast=0 or signal=0 must raise ValueError."""
        close = pd.Series([1.0, 2.0, 3.0], dtype=np.float64)
        with pytest.raises(ValueError):
            compute_macd_histogram(close, fast=0, slow=3, signal=2)
        with pytest.raises(ValueError):
            compute_macd_histogram(close, fast=1, slow=3, signal=0)


class TestComputeAdx:
    """Tests for compute_adx (Average Directional Index)."""

    def test_known_values_period_2(self) -> None:
        """Verify ADX values match hand-computed Wilder's smoothing for period=2."""
        high = pd.Series([12.0, 14.0, 16.0, 15.0, 17.0], dtype=np.float64)
        low = pd.Series([8.0, 9.0, 11.0, 10.0, 12.0], dtype=np.float64)
        close = pd.Series([10.0, 13.0, 15.0, 12.0, 16.0], dtype=np.float64)
        result = compute_adx(high, low, close, period=2)

        # +DI: [NaN, NaN, 40.0, 20.0, 30.0]
        assert pd.isna(result["plus_di"].iloc[0])
        assert pd.isna(result["plus_di"].iloc[1])
        assert result["plus_di"].iloc[2] == pytest.approx(40.0, abs=1e-4)
        assert result["plus_di"].iloc[3] == pytest.approx(20.0, abs=1e-4)
        assert result["plus_di"].iloc[4] == pytest.approx(30.0, abs=1e-4)

        # -DI: [NaN, NaN, 0.0, 10.0, 5.0]
        # (Spec table had arithmetic error: 0*0.5+1=1.0, not 0.5)
        assert pd.isna(result["minus_di"].iloc[0])
        assert pd.isna(result["minus_di"].iloc[1])
        assert result["minus_di"].iloc[2] == pytest.approx(0.0, abs=1e-4)
        assert result["minus_di"].iloc[3] == pytest.approx(10.0, abs=1e-4)
        assert result["minus_di"].iloc[4] == pytest.approx(5.0, abs=1e-4)

        # ADX: [NaN, NaN, NaN, 200/3, 1450/21]
        # DX[2]=100, DX[3]=100/3; ADX[3]=mean(100, 100/3)=200/3
        # DX[4]=500/7; ADX[4]=(200/3*1 + 500/7)/2 = 1450/21*1/2... wait
        # ADX[4] = (ADX[3]*(2-1) + DX[4]) / 2 = (200/3 + 500/7)/2 = 2900/42 = 1450/21
        assert pd.isna(result["adx"].iloc[0])
        assert pd.isna(result["adx"].iloc[1])
        assert pd.isna(result["adx"].iloc[2])
        assert result["adx"].iloc[3] == pytest.approx(200.0 / 3.0, abs=1e-4)
        assert result["adx"].iloc[4] == pytest.approx(1450.0 / 21.0, abs=1e-4)

    def test_flat_market_no_crash(self) -> None:
        """Flat market (TR=0) should produce DI=0, ADX=0, not crash."""
        high = pd.Series([10.0] * 8, dtype=np.float64)
        low = pd.Series([10.0] * 8, dtype=np.float64)
        close = pd.Series([10.0] * 8, dtype=np.float64)
        result = compute_adx(high, low, close, period=3)
        # After warmup, DI values should be exactly 0.0
        for i in range(3, 8):
            assert result["plus_di"].iloc[i] == 0.0
            assert result["minus_di"].iloc[i] == 0.0
        # ADX after warmup should be 0.0
        for i in range(5, 8):
            assert result["adx"].iloc[i] == 0.0

    def test_downtrend_minus_di_dominates(self) -> None:
        """In a downtrend, -DI should exceed +DI."""
        # Steadily declining highs and lows
        high = pd.Series([20.0, 19.0, 18.0, 17.0, 16.0, 15.0], dtype=np.float64)
        low = pd.Series([18.0, 17.0, 16.0, 15.0, 14.0, 13.0], dtype=np.float64)
        close = pd.Series([19.0, 18.0, 17.0, 16.0, 15.0, 14.0], dtype=np.float64)
        result = compute_adx(high, low, close, period=2)
        # After warmup (index >= 2), -DI should be > +DI
        for i in range(2, 6):
            assert result["minus_di"].iloc[i] > result["plus_di"].iloc[i]
        # ADX should be high (strong trend)
        assert result["adx"].iloc[-1] > 50.0

    def test_strong_uptrend(self) -> None:
        """Steadily increasing prices: +DI > -DI, ADX > 25 eventually."""
        n = 30
        high = pd.Series([10.0 + i * 2.0 for i in range(n)], dtype=np.float64)
        low = pd.Series([8.0 + i * 2.0 for i in range(n)], dtype=np.float64)
        close = pd.Series([9.0 + i * 2.0 for i in range(n)], dtype=np.float64)
        result = compute_adx(high, low, close, period=3)

        # After warmup, +DI should dominate -DI
        valid_mask = ~pd.isna(result["plus_di"])
        assert (result["plus_di"][valid_mask] > result["minus_di"][valid_mask]).all()

        # ADX should be > 25 at the end (strong trend)
        assert result["adx"].iloc[-1] > 25.0

    def test_warmup_nan_default_period(self) -> None:
        """Default period=14: first 13 DI NaN, first 27 ADX NaN."""
        n = 50
        high = pd.Series([100.0 + float(i) for i in range(n)], dtype=np.float64)
        low = pd.Series([98.0 + float(i) for i in range(n)], dtype=np.float64)
        close = pd.Series([99.0 + float(i) for i in range(n)], dtype=np.float64)
        result = compute_adx(high, low, close)

        # First 14 values (indices 0-13) of +DI/-DI are NaN
        for i in range(14):
            assert pd.isna(result["plus_di"].iloc[i]), f"+DI NaN at {i}"
            assert pd.isna(result["minus_di"].iloc[i]), f"-DI NaN at {i}"
        assert not pd.isna(result["plus_di"].iloc[14])

        # First 27 values (indices 0-26) of ADX are NaN (2*14 - 1 = 27)
        for i in range(27):
            assert pd.isna(result["adx"].iloc[i]), f"ADX NaN at {i}"
        assert not pd.isna(result["adx"].iloc[27])

    def test_invalid_period_raises(self) -> None:
        """period=1 or period=0 must raise ValueError."""
        high = pd.Series([1.0, 2.0, 3.0], dtype=np.float64)
        low = pd.Series([0.5, 1.5, 2.5], dtype=np.float64)
        close = pd.Series([0.8, 1.8, 2.8], dtype=np.float64)
        with pytest.raises(ValueError, match="period must be >= 2"):
            compute_adx(high, low, close, period=1)
        with pytest.raises(ValueError, match="period must be >= 2"):
            compute_adx(high, low, close, period=0)

    def test_returns_dataframe_columns(self) -> None:
        """Return value is a DataFrame with columns plus_di, minus_di, adx."""
        high = pd.Series([12.0, 14.0, 16.0, 15.0, 17.0], dtype=np.float64)
        low = pd.Series([8.0, 9.0, 11.0, 10.0, 12.0], dtype=np.float64)
        close = pd.Series([10.0, 13.0, 15.0, 12.0, 16.0], dtype=np.float64)
        result = compute_adx(high, low, close, period=2)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["plus_di", "minus_di", "adx"]
        assert len(result) == len(high)


class TestComputeAtr:
    """Tests for compute_atr (Average True Range, Wilder's smoothing)."""

    def test_known_values_period_3(self) -> None:
        """Verify ATR against hand-calculated values for period=3."""
        high = pd.Series([12.0, 14.0, 15.0, 13.0, 16.0, 17.0, 15.0], dtype=np.float64)
        low = pd.Series([8.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0], dtype=np.float64)
        close = pd.Series([10.0, 13.0, 14.0, 12.0, 15.0, 16.0, 13.0], dtype=np.float64)
        result = compute_atr(high, low, close, period=3)

        # First 3 values (indices 0-2) must be NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert pd.isna(result.iloc[2])

        # ATR[3] = mean(5, 5, 3) = 13/3
        assert result.iloc[3] == pytest.approx(13.0 / 3.0, abs=1e-4)
        # ATR[4] = (13/3 * 2 + 6) / 3 = 44/9
        assert result.iloc[4] == pytest.approx(44.0 / 9.0, abs=1e-4)
        # ATR[5] = (44/9 * 2 + 5) / 3 = 133/27
        assert result.iloc[5] == pytest.approx(133.0 / 27.0, abs=1e-4)
        # ATR[6] = (133/27 * 2 + 5) / 3 = 401/81
        assert result.iloc[6] == pytest.approx(401.0 / 81.0, abs=1e-4)

    def test_flat_market_atr_zero(self) -> None:
        """When high == low == close for all bars, ATR = 0."""
        high = pd.Series([100.0] * 6, dtype=np.float64)
        low = pd.Series([100.0] * 6, dtype=np.float64)
        close = pd.Series([100.0] * 6, dtype=np.float64)
        result = compute_atr(high, low, close, period=3)
        for i in range(3, 6):
            assert result.iloc[i] == pytest.approx(0.0)

    def test_warmup_nan(self) -> None:
        """First period values should be NaN, index period should be a valid float."""
        n = 30
        high = pd.Series([10.0 + float(i) * 2.0 for i in range(n)], dtype=np.float64)
        low = pd.Series([8.0 + float(i) * 2.0 for i in range(n)], dtype=np.float64)
        close = pd.Series([9.0 + float(i) * 2.0 for i in range(n)], dtype=np.float64)
        result = compute_atr(high, low, close, period=14)

        for i in range(14):
            assert pd.isna(result.iloc[i]), f"Expected NaN at index {i}"
        assert not pd.isna(result.iloc[14])
        assert isinstance(result.iloc[14], float)

    def test_invalid_period_raises(self) -> None:
        """period < 1 raises ValueError."""
        close = pd.Series([1.0, 2.0], dtype=np.float64)
        with pytest.raises(ValueError, match="period must be >= 1"):
            compute_atr(close, close, close, period=0)

    def test_volatile_higher_than_flat(self) -> None:
        """Volatile data should have higher ATR than stable (flat-range) data."""
        n = 20
        # Volatile: wide range between high and low
        v_high = pd.Series([100.0 + 10.0 * (i % 2) for i in range(n)], dtype=np.float64)
        v_low = pd.Series([100.0 - 10.0 * (i % 2) for i in range(n)], dtype=np.float64)
        v_close = pd.Series([100.0] * n, dtype=np.float64)
        # Flat: tight range
        f_high = pd.Series([100.1] * n, dtype=np.float64)
        f_low = pd.Series([99.9] * n, dtype=np.float64)
        f_close = pd.Series([100.0] * n, dtype=np.float64)

        period = 5
        atr_volatile = compute_atr(v_high, v_low, v_close, period=period)
        atr_flat = compute_atr(f_high, f_low, f_close, period=period)

        assert atr_volatile.iloc[-1] > atr_flat.iloc[-1]


class TestComputeWickRatios:
    """Tests for compute_wick_ratios."""

    def test_known_values(self) -> None:
        """Verify wick ratios match pre-computed values for 4-row OHLC example."""
        data = {
            "open": [10.0, 12.0, 11.0, 10.0],
            "high": [14.0, 15.0, 11.0, 14.0],
            "low": [8.0, 9.0, 11.0, 10.0],
            "close": [12.0, 10.0, 11.0, 14.0],
        }
        df = pd.DataFrame(data, dtype=np.float64)
        result = compute_wick_ratios(df)

        # Row 0: bullish (C>O) → upper=(14-12)/(14-8)=2/6, lower=(10-8)/(14-8)=2/6
        assert result["upper_wick_ratio"].iloc[0] == pytest.approx(1 / 3, abs=1e-5)
        assert result["lower_wick_ratio"].iloc[0] == pytest.approx(1 / 3, abs=1e-5)

        # Row 1: bearish (C<O) → upper=(15-12)/(15-9)=3/6=0.5, lower=(10-9)/(15-9)=1/6
        assert result["upper_wick_ratio"].iloc[1] == pytest.approx(0.5, abs=1e-5)
        assert result["lower_wick_ratio"].iloc[1] == pytest.approx(1 / 6, abs=1e-5)

        # Row 2: doji (H=L=O=C=11) → zero range → both 0.0
        assert result["upper_wick_ratio"].iloc[2] == pytest.approx(0.0, abs=1e-5)
        assert result["lower_wick_ratio"].iloc[2] == pytest.approx(0.0, abs=1e-5)

        # Row 3: full body (O=L=10, C=H=14) → no wicks → both 0.0
        assert result["upper_wick_ratio"].iloc[3] == pytest.approx(0.0, abs=1e-5)
        assert result["lower_wick_ratio"].iloc[3] == pytest.approx(0.0, abs=1e-5)

    def test_zero_range_returns_zero(self) -> None:
        """When high == low, both wick ratios must be 0.0 (no divide-by-zero crash)."""
        df = pd.DataFrame(
            {"open": [10.0], "high": [10.0], "low": [10.0], "close": [10.0]},
            dtype=np.float64,
        )
        result = compute_wick_ratios(df)

        assert result["upper_wick_ratio"].iloc[0] == pytest.approx(0.0)
        assert result["lower_wick_ratio"].iloc[0] == pytest.approx(0.0)

    def test_full_body_no_wicks(self) -> None:
        """open==low and close==high → zero wicks on both sides."""
        df = pd.DataFrame(
            {"open": [5.0], "high": [10.0], "low": [5.0], "close": [10.0]},
            dtype=np.float64,
        )
        result = compute_wick_ratios(df)

        assert result["upper_wick_ratio"].iloc[0] == pytest.approx(0.0)
        assert result["lower_wick_ratio"].iloc[0] == pytest.approx(0.0)

    def test_ratios_between_0_and_1(self) -> None:
        """All wick ratio values must lie in [0.0, 1.0]."""
        rng = np.random.default_rng(42)
        n = 50
        lows = rng.uniform(1.0, 50.0, n)
        highs = lows + rng.uniform(0.0, 10.0, n)
        opens = lows + rng.uniform(0.0, 1.0, n) * (highs - lows)
        closes = lows + rng.uniform(0.0, 1.0, n) * (highs - lows)
        df = pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes},
            dtype=np.float64,
        )
        result = compute_wick_ratios(df)

        assert (result["upper_wick_ratio"] >= 0.0).all()
        assert (result["upper_wick_ratio"] <= 1.0).all()
        assert (result["lower_wick_ratio"] >= 0.0).all()
        assert (result["lower_wick_ratio"] <= 1.0).all()


class TestComputeDistanceFrom20dLow:
    """Tests for compute_distance_from_20d_low."""

    def test_known_values_window_3(self) -> None:
        """Verify distance values match pre-computed results with window=3."""
        close = pd.Series([100.0, 102.0, 105.0, 103.0, 107.0], dtype=np.float64)
        low = pd.Series([98.0, 99.0, 100.0, 97.0, 101.0], dtype=np.float64)
        result = compute_distance_from_20d_low(close, low, window=3)

        # First 2 (window-1) values must be NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])

        # i=2: rolling_min(98,99,100)=98 → (105-98)/105 = 7/105
        assert result.iloc[2] == pytest.approx(7.0 / 105.0, abs=1e-5)

        # i=3: rolling_min(99,100,97)=97 → (103-97)/103 = 6/103
        assert result.iloc[3] == pytest.approx(6.0 / 103.0, abs=1e-5)

        # i=4: rolling_min(100,97,101)=97 → (107-97)/107 = 10/107
        assert result.iloc[4] == pytest.approx(10.0 / 107.0, abs=1e-5)

    def test_at_low_returns_zero(self) -> None:
        """When close equals the rolling minimum low, distance must be 0.0."""
        close = pd.Series([10.0, 10.0, 10.0], dtype=np.float64)
        low = pd.Series([10.0, 10.0, 10.0], dtype=np.float64)
        result = compute_distance_from_20d_low(close, low, window=3)

        assert result.iloc[2] == pytest.approx(0.0)

    def test_warmup_nan(self) -> None:
        """First window-1 values must be NaN; index window-1 must be valid."""
        n = 25
        close = pd.Series([100.0 + float(i) for i in range(n)], dtype=np.float64)
        low = pd.Series([99.0 + float(i) for i in range(n)], dtype=np.float64)
        result = compute_distance_from_20d_low(close, low, window=20)

        for i in range(19):
            assert pd.isna(result.iloc[i]), f"Expected NaN at index {i}"
        assert not pd.isna(result.iloc[19])

    def test_invalid_window_raises(self) -> None:
        """window < 1 must raise ValueError."""
        close = pd.Series([100.0, 101.0, 102.0], dtype=np.float64)
        low = pd.Series([99.0, 100.0, 101.0], dtype=np.float64)
        with pytest.raises(ValueError):
            compute_distance_from_20d_low(close, low, window=0)


class TestComputeRelativeStrengthVsUsd:
    """Tests for compute_relative_strength_vs_usd (rolling z-score of XAU/EUR ratio)."""

    def test_known_values_window_3(self) -> None:
        """Verify z-score values match pre-computed results for window=3, EUR/USD=1.0."""
        xau_close = pd.Series([10.0, 12.0, 14.0, 10.0, 12.0], dtype=np.float64)
        eurusd_close = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
        result = compute_relative_strength_vs_usd(xau_close, eurusd_close, window=3)

        # First 2 (window-1) values must be NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])

        # i=2: ratio=[10,12,14], mean=12, std=2, z=(14-12)/2 = 1.0
        assert result.iloc[2] == pytest.approx(1.0, abs=1e-5)
        # i=3: ratio=[12,14,10], mean=12, std=2, z=(10-12)/2 = -1.0
        assert result.iloc[3] == pytest.approx(-1.0, abs=1e-5)
        # i=4: ratio=[14,10,12], mean=12, std=2, z=(12-12)/2 = 0.0
        assert result.iloc[4] == pytest.approx(0.0, abs=1e-5)

    def test_varying_eurusd(self) -> None:
        """Verify z-score with varying EUR/USD values (window=3)."""
        xau_close = pd.Series([10.0, 12.0, 14.0], dtype=np.float64)
        eurusd_close = pd.Series([1.0, 2.0, 1.0], dtype=np.float64)
        result = compute_relative_strength_vs_usd(xau_close, eurusd_close, window=3)

        # Ratio = [10.0, 6.0, 14.0]
        # Mean = 10.0, Std = sqrt((0+16+16)/2) = 4.0
        # Z at index 2 = (14 - 10) / 4 = 1.0
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(1.0, abs=1e-5)

    def test_constant_ratio_nan(self) -> None:
        """Constant ratio → std = 0 → z-score is NaN (IEEE float division)."""
        xau_close = pd.Series([100.0, 100.0, 100.0], dtype=np.float64)
        eurusd_close = pd.Series([1.0, 1.0, 1.0], dtype=np.float64)
        result = compute_relative_strength_vs_usd(xau_close, eurusd_close, window=3)

        # All warmup NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        # std = 0 → NaN (not a crash)
        assert pd.isna(result.iloc[2])

    def test_warmup_nan(self) -> None:
        """First window-1 values must be NaN; index window-1 must be non-NaN."""
        n = 25
        xau_close = pd.Series([1900.0 + float(i) for i in range(n)], dtype=np.float64)
        eurusd_close = pd.Series([1.1] * n, dtype=np.float64)
        result = compute_relative_strength_vs_usd(xau_close, eurusd_close, window=20)

        for i in range(19):
            assert pd.isna(result.iloc[i]), f"Expected NaN at index {i}"
        assert not pd.isna(result.iloc[19])

    def test_invalid_window_raises(self) -> None:
        """window < 1 must raise ValueError."""
        xau_close = pd.Series([100.0, 101.0, 102.0], dtype=np.float64)
        eurusd_close = pd.Series([1.0, 1.0, 1.0], dtype=np.float64)
        with pytest.raises(ValueError, match="window must be >= 1"):
            compute_relative_strength_vs_usd(xau_close, eurusd_close, window=0)
