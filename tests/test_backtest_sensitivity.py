"""Tests for parameter sensitivity analysis and guard ablation."""

from typing import Any

import pandas as pd
import pytest

from trading_advisor.backtest.sensitivity import (
    SensitivityResult,
    run_atr_multiplier_sensitivity,
    run_ema_sensitivity,
    run_fill_price_sensitivity,
    run_guard_ablation,
    run_momentum_lookback_sensitivity,
    run_threshold_sensitivity,
    run_tp_sensitivity,
)
from trading_advisor.guards.base import Guard, GuardResult

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_EXPECTED_METRIC_KEYS = {
    "sharpe_ratio",
    "max_drawdown_pct",
    "win_rate",
    "total_trades",
}


class _StubGuard(Guard):
    """Guard that always passes, for testing."""

    def __init__(self, guard_name: str) -> None:
        self._name = guard_name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, **kwargs: object) -> GuardResult:
        return GuardResult(passed=True, guard_name=self._name, reason="stub")


def _make_indicators(n: int, **overrides: Any) -> pd.DataFrame:
    """Build n rows of synthetic indicator data with sensible defaults."""
    dates = pd.bdate_range("2024-01-01", periods=n, freq="B")
    data: dict[str, Any] = {
        "open": [2000.0] * n,
        "high": [2010.0] * n,
        "low": [1990.0] * n,
        "close": [2000.0] * n,
        "atr_14": [50.0] * n,
        "adx_14": [30.0] * n,
        "ema_8": [2000.0] * n,
        "ema_20": [2000.0] * n,
        "ema_50": [2000.0] * n,
        "sma_50": [2000.0] * n,
        "sma_200": [2000.0] * n,
        "rsi_14": [50.0] * n,
        "composite": [0.0] * n,
        "signal": ["NEUTRAL"] * n,
        "momentum_z": [0.0] * n,
        "trend_z": [0.0] * n,
        "rsi_filter_z": [0.0] * n,
        "atr_volatility_z": [0.0] * n,
        "sr_proximity_z": [0.0] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data, index=dates)


def _make_eurusd(n: int) -> pd.DataFrame:
    """Build n rows of synthetic EUR/USD data."""
    dates = pd.bdate_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": [1.10] * n, "sma_200": [1.08] * n}, index=dates)


def _empty_fedfunds() -> "pd.Series[float]":
    """Return an empty FEDFUNDS series."""
    return pd.Series([], dtype=float)


def _make_ohlcv(n: int) -> pd.DataFrame:
    """Build n rows of synthetic OHLCV data suitable for indicator computation."""
    dates = pd.bdate_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": [2000.0] * n,
            "high": [2010.0] * n,
            "low": [1990.0] * n,
            "close": [2000.0] * n,
        },
        index=dates,
    )


def _make_eurusd_raw(n: int) -> pd.DataFrame:
    """Build n rows of raw EUR/USD data (no sma_200 column)."""
    dates = pd.bdate_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": [1.10] * n}, index=dates)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSensitivityResultFrozen:
    """SensitivityResult is immutable."""

    def test_sensitivity_result_frozen(self) -> None:
        """Cannot assign to attributes after creation."""
        result = SensitivityResult(
            param_name="test",
            param_value="1.0",
            metrics={"sharpe_ratio": 0.5},
        )
        with pytest.raises(AttributeError):
            result.param_name = "changed"  # type: ignore[misc]


class TestThresholdSensitivity:
    """run_threshold_sensitivity tests."""

    def test_threshold_sensitivity_default_thresholds(self) -> None:
        """Default thresholds produce 7 results with correct param_name."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_threshold_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
        )

        assert len(results) == 7
        for r in results:
            assert r.param_name == "composite_buy_threshold"
        expected_values = ["1.0", "1.25", "1.5", "1.75", "2.0", "2.25", "2.5"]
        assert [r.param_value for r in results] == expected_values

    def test_threshold_sensitivity_custom(self) -> None:
        """Custom thresholds produce the correct count."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_threshold_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            thresholds=[0.5, 1.0, 1.5],
        )

        assert len(results) == 3
        assert [r.param_value for r in results] == ["0.5", "1.0", "1.5"]


class TestAtrMultiplierSensitivity:
    """run_atr_multiplier_sensitivity tests."""

    def test_atr_multiplier_sensitivity(self) -> None:
        """Default multipliers produce 4 results."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_atr_multiplier_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
        )

        assert len(results) == 4
        for r in results:
            assert r.param_name == "atr_multiplier"
        expected_values = ["1.5", "2.0", "2.5", "3.0"]
        assert [r.param_value for r in results] == expected_values

    def test_atr_multiplier_sensitivity_custom(self) -> None:
        """Custom multipliers produce the correct count."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_atr_multiplier_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            multipliers=[1.0, 3.5],
        )

        assert len(results) == 2
        assert [r.param_value for r in results] == ["1.0", "3.5"]


class TestTpSensitivity:
    """run_tp_sensitivity tests."""

    def test_tp_sensitivity(self) -> None:
        """Default clamp ranges produce 8 results."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_tp_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
        )

        assert len(results) == 8
        for r in results:
            assert r.param_name == "tp_clamp"
        expected_values = [
            "(2.0, 3.5)",
            "(2.0, 4.5)",
            "(2.0, 5.0)",
            "(2.5, 4.0)",
            "(2.5, 4.5)",
            "(2.5, 5.0)",
            "(3.0, 4.5)",
            "(3.0, 5.0)",
        ]
        assert [r.param_value for r in results] == expected_values

    def test_tp_sensitivity_custom(self) -> None:
        """Custom clamp ranges produce the correct count."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_tp_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            clamp_ranges=[(2.0, 4.0)],
        )

        assert len(results) == 1
        assert results[0].param_value == "(2.0, 4.0)"


class TestMomentumLookbackSensitivity:
    """run_momentum_lookback_sensitivity tests."""

    def test_momentum_lookback_sensitivity(self) -> None:
        """Default lookbacks produce 4 results."""
        n = 600
        ohlcv = _make_ohlcv(n)
        eurusd = _make_eurusd_raw(n)

        results = run_momentum_lookback_sensitivity(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
        )

        assert len(results) == 4
        for r in results:
            assert r.param_name == "momentum_lookback"
        expected_values = ["63", "126", "189", "252"]
        assert [r.param_value for r in results] == expected_values

    def test_momentum_lookback_sensitivity_custom(self) -> None:
        """Custom lookbacks produce the correct count."""
        n = 600
        ohlcv = _make_ohlcv(n)
        eurusd = _make_eurusd_raw(n)

        results = run_momentum_lookback_sensitivity(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            lookbacks=[63, 126],
        )

        assert len(results) == 2
        assert [r.param_value for r in results] == ["63", "126"]

    def test_momentum_lookback_eurusd_with_sma(self) -> None:
        """When eurusd already has sma_200 it is passed through unchanged."""
        n = 600
        ohlcv = _make_ohlcv(n)
        dates = pd.bdate_range("2020-01-01", periods=n, freq="B")
        eurusd_with_sma = pd.DataFrame({"close": [1.10] * n, "sma_200": [1.08] * n}, index=dates)

        results = run_momentum_lookback_sensitivity(
            ohlcv=ohlcv,
            eurusd=eurusd_with_sma,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            lookbacks=[63],
        )

        assert len(results) == 1


class TestEmaSensitivity:
    """run_ema_sensitivity tests."""

    def test_ema_sensitivity(self) -> None:
        """Default EMA sets produce 3 results."""
        n = 600
        ohlcv = _make_ohlcv(n)
        eurusd = _make_eurusd_raw(n)

        results = run_ema_sensitivity(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
        )

        assert len(results) == 3
        for r in results:
            assert r.param_name == "ema_periods"
        expected_values = ["(8, 20, 50)", "(10, 21, 55)", "(12, 26, 50)"]
        assert [r.param_value for r in results] == expected_values

    def test_ema_sensitivity_custom(self) -> None:
        """Custom EMA sets produce the correct count."""
        n = 600
        ohlcv = _make_ohlcv(n)
        eurusd = _make_eurusd_raw(n)

        results = run_ema_sensitivity(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            ema_sets=[(8, 20, 50)],
        )

        assert len(results) == 1
        assert results[0].param_value == "(8, 20, 50)"


class TestFillPriceSensitivity:
    """run_fill_price_sensitivity tests."""

    def test_fill_price_sensitivity(self) -> None:
        """Always produces 2 results: buy_stop and midpoint."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_fill_price_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
        )

        assert len(results) == 2
        for r in results:
            assert r.param_name == "fill_price_offset"
        assert results[0].param_value == "0.0"
        assert results[1].param_value == "0.5"


class TestGuardAblation:
    """run_guard_ablation tests."""

    def test_guard_ablation(self) -> None:
        """Baseline + one per guard = N+1 results."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        guards = [_StubGuard("GuardA"), _StubGuard("GuardB")]
        guards_enabled = {"GuardA": True, "GuardB": True}

        results = run_guard_ablation(
            indicators=indicators,
            eurusd=eurusd,
            guards=guards,
            guards_enabled=guards_enabled,
            fedfunds=_empty_fedfunds(),
        )

        # baseline + 2 ablations
        assert len(results) == 3
        assert results[0].param_name == "guard_ablation"
        assert results[0].param_value == "baseline"
        assert results[1].param_value == "without_GuardA"
        assert results[2].param_value == "without_GuardB"


class TestMetricsKeysPresent:
    """Metrics dictionaries include expected keys."""

    def test_metrics_keys_present(self) -> None:
        """All results from threshold sensitivity contain expected metric keys."""
        n = 20
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        results = run_threshold_sensitivity(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            thresholds=[1.5],
        )

        assert len(results) == 1
        for key in _EXPECTED_METRIC_KEYS:
            assert key in results[0].metrics, f"Missing metric key: {key}"
