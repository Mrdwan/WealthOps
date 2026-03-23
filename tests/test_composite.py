"""Tests for momentum composite calculation and signal classification."""

import numpy as np
import pandas as pd
import pytest

from trading_advisor.indicators.composite import Signal, rolling_zscore


class TestSignal:
    def test_all_values(self) -> None:
        """Signal enum has all 5 expected values."""
        assert Signal.STRONG_BUY.value == "STRONG_BUY"
        assert Signal.BUY.value == "BUY"
        assert Signal.NEUTRAL.value == "NEUTRAL"
        assert Signal.SELL.value == "SELL"
        assert Signal.STRONG_SELL.value == "STRONG_SELL"
        assert len(Signal) == 5


class TestRollingZscore:
    def test_linear_sequence(self) -> None:
        """Linear ascending sequence: z-score = 1.0 at each position."""
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(1.0)
        assert result.iloc[3] == pytest.approx(1.0)
        assert result.iloc[4] == pytest.approx(1.0)

    def test_zero_std_nan(self) -> None:
        """Constant values (zero std) produce NaN, not inf."""
        series = pd.Series([5.0, 5.0, 5.0, 5.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        assert pd.isna(result.iloc[2])
        assert pd.isna(result.iloc[3])
        # Verify it's NaN, not inf
        assert not np.isinf(result.iloc[2])

    def test_short_series_all_nan(self) -> None:
        """Series shorter than window produces all NaN."""
        series = pd.Series([1.0, 2.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        assert result.isna().all()

    def test_negative_zscore(self) -> None:
        """Value below mean gives negative z-score."""
        series = pd.Series([10.0, 12.0, 8.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        # mean=10, std=2, z=(8-10)/2=-1.0
        assert result.iloc[2] == pytest.approx(-1.0)

    def test_default_window_252(self) -> None:
        """Default window is 252. First 251 values should be NaN."""
        series = pd.Series(np.arange(260, dtype=np.float64))
        result = rolling_zscore(series)
        assert result.iloc[:251].isna().all()
        assert not pd.isna(result.iloc[251])

    def test_invalid_window_raises(self) -> None:
        """window < 2 raises ValueError."""
        series = pd.Series([1.0, 2.0], dtype=np.float64)
        with pytest.raises(ValueError, match="window must be >= 2"):
            rolling_zscore(series, window=1)
