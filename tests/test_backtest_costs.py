"""Tests for backtest cost-model functions."""

import pandas as pd
import pytest

from trading_advisor.backtest.engine import (
    compute_overnight_funding,
    compute_round_trip_cost,
    get_fedfunds_rate,
)


class TestComputeRoundTripCost:
    """Tests for compute_round_trip_cost."""

    def test_standard_size(self) -> None:
        """Round-trip costs for size=0.05, spread=0.3, slippage=0.1."""
        spread, slippage = compute_round_trip_cost(0.05, 0.3, 0.1)
        assert spread == pytest.approx(0.03)
        assert slippage == pytest.approx(0.01)

    def test_unit_size(self) -> None:
        """Round-trip costs for size=1.0."""
        spread, slippage = compute_round_trip_cost(1.0, 0.3, 0.1)
        assert spread == pytest.approx(0.6)
        assert slippage == pytest.approx(0.2)

    def test_small_size(self) -> None:
        """Round-trip costs for size=0.01."""
        spread, slippage = compute_round_trip_cost(0.01, 0.3, 0.1)
        assert spread == pytest.approx(0.006)
        assert slippage == pytest.approx(0.002)

    def test_zero_size(self) -> None:
        """Zero size produces zero costs."""
        spread, slippage = compute_round_trip_cost(0.0, 0.3, 0.1)
        assert spread == 0.0
        assert slippage == 0.0

    def test_zero_spread(self) -> None:
        """Zero spread, nonzero slippage."""
        spread, slippage = compute_round_trip_cost(0.05, 0.0, 0.1)
        assert spread == 0.0
        assert slippage == pytest.approx(0.01)


class TestComputeOvernightFunding:
    """Tests for compute_overnight_funding."""

    def test_standard(self) -> None:
        """Funding for notional=102.5, rate=0.05."""
        # 102.5 * (0.05 + 0.025) / 365 = 102.5 * 0.075 / 365 = 0.02106...
        result = compute_overnight_funding(102.5, 0.05)
        assert result == pytest.approx(102.5 * 0.075 / 365)

    def test_zero_rate(self) -> None:
        """Funding with zero FEDFUNDS rate (still pays admin fee)."""
        # 102.5 * 0.025 / 365
        result = compute_overnight_funding(102.5, 0.0)
        assert result == pytest.approx(102.5 * 0.025 / 365)

    def test_zero_notional(self) -> None:
        """Zero notional produces zero funding."""
        assert compute_overnight_funding(0.0, 0.05) == 0.0

    def test_high_rate(self) -> None:
        """Funding with high FEDFUNDS rate."""
        result = compute_overnight_funding(100.0, 0.10)
        # 100 * (0.10 + 0.025) / 365 = 100 * 0.125 / 365
        assert result == pytest.approx(100.0 * 0.125 / 365)


class TestGetFedfundsRate:
    """Tests for get_fedfunds_rate."""

    def _make_series(self) -> "pd.Series[float]":
        """Create a sample FEDFUNDS series (FRED publishes as percentages)."""
        dates = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])
        return pd.Series([5.0, 4.5, 4.0], index=dates)

    def test_exact_date(self) -> None:
        """Exact date match returns that rate converted to decimal."""
        s = self._make_series()
        assert get_fedfunds_rate(s, pd.Timestamp("2024-02-01")) == pytest.approx(0.045)

    def test_forward_fill(self) -> None:
        """Date between entries returns most recent prior value as decimal."""
        s = self._make_series()
        assert get_fedfunds_rate(s, pd.Timestamp("2024-02-15")) == pytest.approx(0.045)

    def test_after_all(self) -> None:
        """Date after all entries returns the last value as decimal."""
        s = self._make_series()
        assert get_fedfunds_rate(s, pd.Timestamp("2024-06-01")) == pytest.approx(0.04)

    def test_before_all(self) -> None:
        """Date before all entries returns 0.0."""
        s = self._make_series()
        assert get_fedfunds_rate(s, pd.Timestamp("2023-01-01")) == 0.0

    def test_empty_series(self) -> None:
        """Empty series returns 0.0."""
        s: pd.Series[float] = pd.Series([], dtype=float)
        assert get_fedfunds_rate(s, pd.Timestamp("2024-01-01")) == 0.0
