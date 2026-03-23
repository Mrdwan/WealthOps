"""Tests for technical indicators."""

import numpy as np
import pandas as pd
import pytest

from trading_advisor.indicators.technical import (
    compute_ema,
    compute_ema_fan,
    compute_macd_histogram,
    compute_rsi,
    compute_sma,
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
