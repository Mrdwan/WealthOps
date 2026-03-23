"""Tests for technical indicators."""

import numpy as np
import pandas as pd
import pytest

from trading_advisor.indicators.technical import compute_rsi


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
