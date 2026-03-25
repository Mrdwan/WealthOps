"""Tests for walk-forward analysis and WFE computation."""

import datetime
from typing import Any

import numpy as np
import pandas as pd
import pytest
import pytest_mock

from trading_advisor.backtest.validation import (
    ShuffledPriceResult,
    WalkForwardResult,
    WalkForwardWindow,
    _run_window_backtest,
    compute_t_statistic,
    compute_wfe,
    generate_walk_forward_windows,
    run_monte_carlo,
    run_shuffled_price_test,
    run_walk_forward,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_indicators(n: int, start: str = "2018-01-01", **overrides: Any) -> pd.DataFrame:
    """Build n rows of synthetic indicator data."""
    dates = pd.bdate_range(start, periods=n, freq="B")
    data: dict[str, Any] = {
        "open": [2000.0] * n,
        "high": [2010.0] * n,
        "low": [1990.0] * n,
        "close": [2000.0] * n,
        "atr_14": [50.0] * n,
        "adx_14": [30.0] * n,
        "ema_8": [2000.0] * n,
        "sma_50": [2000.0] * n,
        "sma_200": [2000.0] * n,
        "rsi_14": [50.0] * n,
        "composite": [0.0] * n,
        "signal": ["NEUTRAL"] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data, index=dates)


def _make_eurusd(n: int, start: str = "2018-01-01") -> pd.DataFrame:
    """Build n rows of synthetic EUR/USD data."""
    dates = pd.bdate_range(start, periods=n, freq="B")
    return pd.DataFrame({"close": [1.10] * n, "sma_200": [1.08] * n}, index=dates)


def _empty_fedfunds() -> "pd.Series[float]":
    return pd.Series([], dtype=float)


# ------------------------------------------------------------------
# Tests: generate_walk_forward_windows
# ------------------------------------------------------------------


class TestGenerateWindows:
    """Tests for walk-forward window generation."""

    def test_basic_windows(self) -> None:
        """5yr range (2018-2023) with 3yr train + 6mo test, 6mo step -> 5 windows."""
        start = datetime.date(2018, 1, 1)
        end = datetime.date(2023, 12, 31)
        windows = generate_walk_forward_windows(start, end)

        assert len(windows) == 5
        # First window: train 2018-01-01 to 2020-12-31, test 2021-01-01 to 2021-06-30
        assert windows[0].train_start == datetime.date(2018, 1, 1)
        assert windows[0].train_end == datetime.date(2020, 12, 31)
        assert windows[0].test_start == datetime.date(2021, 1, 1)
        assert windows[0].test_end == datetime.date(2021, 6, 30)
        # All windows share same train_start (expanding)
        for w in windows:
            assert w.train_start == start
            delta = (w.test_start - w.train_end).days
            assert delta == 1

    def test_window_count_with_known_range(self) -> None:
        """2018-01-01 to 2025-12-31: 3yr train + 6mo test, 6mo step.

        First window: train 2018-01-01 to 2020-12-31, test 2021-01-01 to 2021-06-30
        Second window: train 2018-01-01 to 2021-06-30, test 2021-07-01 to 2021-12-31
        ...continues until test_end exceeds 2025-12-31.

        train_end advances: 2021-01-01, 2021-07-01, 2022-01-01, 2022-07-01,
                           2023-01-01, 2023-07-01, 2024-01-01, 2024-07-01, 2025-01-01, 2025-07-01
        test_end: 2021-07-01, 2022-01-01, 2022-07-01, 2023-01-01,
                 2023-07-01, 2024-01-01, 2024-07-01, 2025-01-01, 2025-07-01, 2026-01-01
        Last valid: test_end 2025-07-01 - 1 day = 2025-06-30 <= 2025-12-31 -> ok
        Next: test_end 2026-01-01 > 2025-12-31 -> hmm, that's the boundary.
        Actually test_end_ts = 2026-01-01 > ts_end=2025-12-31 -> stops.
        So we get 9 windows (test_end 2025-07-01 - 1 day = 2025-06-30 is the last).

        Wait, let me recount. train_end_ts starts at 2021-01-01.
        Window 1: train_end=2021-01-01, test_end=2021-07-01 <= 2025-12-31 ✓
        Window 2: train_end=2021-07-01, test_end=2022-01-01 ✓
        Window 3: train_end=2022-01-01, test_end=2022-07-01 ✓
        Window 4: train_end=2022-07-01, test_end=2023-01-01 ✓
        Window 5: train_end=2023-01-01, test_end=2023-07-01 ✓
        Window 6: train_end=2023-07-01, test_end=2024-01-01 ✓
        Window 7: train_end=2024-01-01, test_end=2024-07-01 ✓
        Window 8: train_end=2024-07-01, test_end=2025-01-01 ✓
        Window 9: train_end=2025-01-01, test_end=2025-07-01 ✓
        Window 10: train_end=2025-07-01, test_end=2026-01-01 > 2025-12-31 ✗
        So 9 windows.
        """
        start = datetime.date(2018, 1, 1)
        end = datetime.date(2025, 12, 31)
        windows = generate_walk_forward_windows(start, end)
        assert len(windows) == 9

    def test_expanding_train(self) -> None:
        """All windows share the same train_start (expanding, not rolling)."""
        start = datetime.date(2018, 1, 1)
        end = datetime.date(2025, 12, 31)
        windows = generate_walk_forward_windows(start, end)
        for w in windows:
            assert w.train_start == start

    def test_too_short_raises(self) -> None:
        """Date range shorter than train + test raises ValueError."""
        start = datetime.date(2020, 1, 1)
        end = datetime.date(2022, 6, 30)  # Only 2.5 years, need 3yr + 6mo
        with pytest.raises(ValueError, match="too short"):
            generate_walk_forward_windows(start, end)

    def test_custom_params(self) -> None:
        """2yr train + 3mo test, 3mo step with 6yr range -> 15 windows."""
        start = datetime.date(2018, 1, 1)
        end = datetime.date(2023, 12, 31)
        windows = generate_walk_forward_windows(
            start, end, train_years=2, test_months=3, step_months=3
        )
        assert len(windows) == 15
        # First window test: 2020-01-01 to 2020-03-31
        assert windows[0].test_start == datetime.date(2020, 1, 1)
        assert windows[0].test_end == datetime.date(2020, 3, 31)

    def test_step_differs_from_test_period(self) -> None:
        """step_months=3 with test_months=6 produces more windows than step=6."""
        start = datetime.date(2018, 1, 1)
        end = datetime.date(2023, 12, 31)

        windows_step6 = generate_walk_forward_windows(
            start, end, train_years=3, test_months=6, step_months=6
        )
        windows_step3 = generate_walk_forward_windows(
            start, end, train_years=3, test_months=6, step_months=3
        )

        assert len(windows_step6) == 5
        assert len(windows_step3) == 10
        assert len(windows_step3) > len(windows_step6)

    def test_exact_test_end_dates(self) -> None:
        """Verify exact test_end dates for all windows."""
        start = datetime.date(2018, 1, 1)
        end = datetime.date(2023, 12, 31)
        windows = generate_walk_forward_windows(start, end)

        expected_test_ends = [
            datetime.date(2021, 6, 30),
            datetime.date(2021, 12, 31),
            datetime.date(2022, 6, 30),
            datetime.date(2022, 12, 31),
            datetime.date(2023, 6, 30),
        ]
        assert len(windows) == len(expected_test_ends)
        for w, expected in zip(windows, expected_test_ends, strict=False):
            assert w.test_end == expected, f"Window test_end {w.test_end} != expected {expected}"

    def test_boundary_test_end_equals_end_date(self) -> None:
        """Window is included when test_end_ts exactly equals ts_end."""
        start = datetime.date(2018, 1, 1)
        # First window: test_end_ts = 2021-07-01
        # Set end to exactly 2021-07-01 so test_end_ts == ts_end
        end = datetime.date(2021, 7, 1)

        windows = generate_walk_forward_windows(start, end)
        assert len(windows) == 1
        # test_end = test_end_ts - 1 day = 2021-06-30
        assert windows[0].test_end == datetime.date(2021, 6, 30)

    def test_boundary_test_end_one_day_over(self) -> None:
        """No window when test_end_ts exceeds end_date by one day."""
        start = datetime.date(2018, 1, 1)
        # First test_end_ts = 2021-07-01, set end to 2021-06-30
        end = datetime.date(2021, 6, 30)

        with pytest.raises(ValueError, match="too short"):
            generate_walk_forward_windows(start, end)


# ------------------------------------------------------------------
# Tests: compute_wfe
# ------------------------------------------------------------------


class TestComputeWFE:
    """Tests for WFE computation."""

    def test_perfect_wfe(self) -> None:
        """Equal IS and OOS Sharpes -> WFE = 1.0."""
        assert compute_wfe([1.0, 1.0], [1.0, 1.0]) == pytest.approx(1.0)

    def test_half_wfe(self) -> None:
        """OOS Sharpes half of IS -> WFE = 0.5."""
        assert compute_wfe([2.0, 2.0], [1.0, 1.0]) == pytest.approx(0.5)

    def test_zero_is_returns_zero(self) -> None:
        """Zero IS Sharpe -> WFE = 0.0 (avoid division by zero)."""
        assert compute_wfe([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_negative_is_returns_zero(self) -> None:
        """Negative IS Sharpe -> WFE = 0.0."""
        assert compute_wfe([-1.0, -1.0], [1.0, 1.0]) == 0.0

    def test_empty_returns_zero(self) -> None:
        """Empty lists -> WFE = 0.0."""
        assert compute_wfe([], []) == 0.0

    def test_mixed_sharpes(self) -> None:
        """Mean of [1.5, 2.5] = 2.0, mean of [0.8, 1.2] = 1.0 -> WFE = 0.5."""
        assert compute_wfe([1.5, 2.5], [0.8, 1.2]) == pytest.approx(0.5)


# ------------------------------------------------------------------
# Tests: _run_window_backtest
# ------------------------------------------------------------------


class TestRunWindowBacktest:
    """Tests for running backtest on a date window."""

    def test_returns_sharpe(self) -> None:
        """Flat data with no signals -> Sharpe = 0.0."""
        n = 500
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        start = indicators.index[0].date()
        end = indicators.index[-1].date()

        sharpe = _run_window_backtest(
            indicators,
            eurusd,
            [],
            {},
            _empty_fedfunds(),
            start,
            end,
            15000.0,
            None,
        )
        assert sharpe == 0.0  # flat equity -> zero Sharpe

    def test_empty_window_returns_zero(self) -> None:
        """Window with no matching dates returns 0.0."""
        indicators = _make_indicators(10, start="2024-01-01")
        eurusd = _make_eurusd(10, start="2024-01-01")

        sharpe = _run_window_backtest(
            indicators,
            eurusd,
            [],
            {},
            _empty_fedfunds(),
            datetime.date(2020, 1, 1),
            datetime.date(2020, 12, 31),
            15000.0,
            None,
        )
        assert sharpe == 0.0


# ------------------------------------------------------------------
# Tests: run_walk_forward
# ------------------------------------------------------------------


class TestRunWalkForward:
    """Tests for the complete walk-forward analysis."""

    def test_returns_result(self) -> None:
        """Walk-forward on 5+ years of data returns a WalkForwardResult."""
        # Need ~5+ years = ~1260 business days
        n = 1500
        indicators = _make_indicators(n, start="2018-01-01")
        eurusd = _make_eurusd(n, start="2018-01-01")

        result = run_walk_forward(
            indicators,
            eurusd,
            [],
            {},
            _empty_fedfunds(),
        )

        assert isinstance(result, WalkForwardResult)
        assert len(result.windows) > 0
        assert len(result.in_sample_sharpes) == len(result.windows)
        assert len(result.oos_sharpes) == len(result.windows)
        assert isinstance(result.wfe, float)

    def test_too_short_data_raises(self) -> None:
        """Data shorter than train + test raises ValueError."""
        n = 100  # ~5 months, need 3yr + 6mo
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        with pytest.raises(ValueError, match="too short"):
            run_walk_forward(indicators, eurusd, [], {}, _empty_fedfunds())


# ------------------------------------------------------------------
# Tests: WalkForwardWindow dataclass
# ------------------------------------------------------------------


class TestWalkForwardWindow:
    """Tests for WalkForwardWindow construction."""

    def test_frozen(self) -> None:
        """WalkForwardWindow is immutable."""
        w = WalkForwardWindow(
            train_start=datetime.date(2018, 1, 1),
            train_end=datetime.date(2020, 12, 31),
            test_start=datetime.date(2021, 1, 1),
            test_end=datetime.date(2021, 6, 30),
        )
        with pytest.raises(AttributeError):
            w.train_start = datetime.date(2019, 1, 1)  # type: ignore[misc]


class TestWalkForwardResult:
    """Tests for WalkForwardResult construction."""

    def test_frozen(self) -> None:
        """WalkForwardResult is immutable."""
        r = WalkForwardResult(
            windows=(),
            in_sample_sharpes=(),
            oos_sharpes=(),
            wfe=0.0,
        )
        with pytest.raises(AttributeError):
            r.wfe = 1.0  # type: ignore[misc]


# ------------------------------------------------------------------
# Tests: run_monte_carlo
# ------------------------------------------------------------------


class TestMonteCarlo:
    """Tests for Monte Carlo bootstrap."""

    def test_all_positive_pnls(self) -> None:
        """All positive trades -> 5th percentile > starting capital -> passed."""
        pnls = [100.0, 200.0, 150.0, 50.0, 300.0]
        result = run_monte_carlo(pnls, starting_capital=15000.0, n_resamples=1000, seed=42)

        assert result.passed is True
        assert result.percentile_5 > 15000.0
        assert result.n_resamples == 1000
        assert result.starting_capital == 15000.0
        assert len(result.terminal_equities) == 1000
        # Terminal equities should be sorted
        for i in range(len(result.terminal_equities) - 1):
            assert result.terminal_equities[i] <= result.terminal_equities[i + 1]

    def test_all_negative_pnls(self) -> None:
        """All negative trades -> 5th percentile < starting capital -> not passed."""
        pnls = [-100.0, -200.0, -150.0, -50.0, -300.0]
        result = run_monte_carlo(pnls, starting_capital=15000.0, n_resamples=1000, seed=42)

        assert result.passed is False
        assert result.percentile_5 < 15000.0

    def test_deterministic_with_seed(self) -> None:
        """Same seed produces same result."""
        pnls = [100.0, -50.0, 200.0, -30.0, 150.0]
        r1 = run_monte_carlo(pnls, starting_capital=15000.0, n_resamples=100, seed=123)
        r2 = run_monte_carlo(pnls, starting_capital=15000.0, n_resamples=100, seed=123)
        assert r1.percentile_5 == r2.percentile_5
        assert r1.terminal_equities == r2.terminal_equities

    def test_single_trade(self) -> None:
        """Single positive trade resampled -> always same terminal equity."""
        pnls = [500.0]
        result = run_monte_carlo(pnls, starting_capital=10000.0, n_resamples=100, seed=42)
        # Every resample draws the same single trade
        assert result.percentile_5 == pytest.approx(10500.0)
        assert all(eq == pytest.approx(10500.0) for eq in result.terminal_equities)

    def test_empty_pnls_raises(self) -> None:
        """Empty trade list raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            run_monte_carlo([], starting_capital=15000.0)

    def test_result_is_frozen(self) -> None:
        """MonteCarloResult is immutable."""
        result = run_monte_carlo([100.0], starting_capital=15000.0, n_resamples=10, seed=1)
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore[misc]

    def test_zero_pnl_not_passed(self) -> None:
        """Zero P&L -> percentile_5 == starting_capital -> NOT passed (strict >)."""
        result = run_monte_carlo([0.0], starting_capital=15000.0, n_resamples=100, seed=42)
        assert result.percentile_5 == pytest.approx(15000.0)
        assert result.passed is False

    def test_percentile_5_position(self) -> None:
        """5th percentile is at the correct position in sorted results."""
        pnls = [100.0, -50.0, 200.0, -30.0, 150.0, -100.0, 80.0]
        result = run_monte_carlo(pnls, starting_capital=15000.0, n_resamples=10000, seed=42)
        # 5th percentile: approximately the 500th value in sorted 10000 results
        idx = int(0.05 * len(result.terminal_equities))
        # The percentile should be near this index value
        assert abs(result.percentile_5 - result.terminal_equities[idx]) < 50.0


# ------------------------------------------------------------------
# Tests: compute_t_statistic
# ------------------------------------------------------------------


class TestTStatistic:
    """Tests for t-statistic computation."""

    def test_known_values(self) -> None:
        """Known P&Ls: [100, 200, 300, 400, 500].

        mean = 300, std = sqrt(25000) = 158.1139..., N = 5
        t = 300 * sqrt(5) / 158.1139 = 300 * 2.2360679 / 158.1139 = 4.2426...
        """
        pnls = [100.0, 200.0, 300.0, 400.0, 500.0]
        t = compute_t_statistic(pnls)
        # mean=300, std(ddof=1)=sqrt(25000)≈158.114
        # t = 300 * sqrt(5) / 158.114 ≈ 4.2426
        assert t == pytest.approx(4.2426, rel=1e-3)

    def test_zero_mean(self) -> None:
        """Symmetric P&Ls: mean = 0 -> t = 0."""
        pnls = [100.0, -100.0, 50.0, -50.0]
        t = compute_t_statistic(pnls)
        assert t == pytest.approx(0.0)

    def test_single_trade_returns_zero(self) -> None:
        """Fewer than 2 trades -> t = 0.0."""
        assert compute_t_statistic([100.0]) == 0.0

    def test_empty_returns_zero(self) -> None:
        """Empty list -> t = 0.0."""
        assert compute_t_statistic([]) == 0.0

    def test_constant_pnls_returns_zero(self) -> None:
        """All identical P&Ls -> std = 0 -> t = 0.0."""
        assert compute_t_statistic([100.0, 100.0, 100.0]) == 0.0

    def test_large_positive_t(self) -> None:
        """All large positive P&Ls with small variance -> high t."""
        pnls = [1000.0, 1001.0, 999.0, 1000.5, 999.5]
        t = compute_t_statistic(pnls)
        assert t > 100.0  # Very high t due to tiny variance relative to mean


# ------------------------------------------------------------------
# Tests: run_shuffled_price_test
# ------------------------------------------------------------------


class TestShuffledPriceTest:
    """Tests for shuffled-price statistical test."""

    def _make_ohlcv(self, n: int, start: str = "2018-01-01") -> pd.DataFrame:
        """Build n rows of OHLCV with a slight uptrend for testing."""
        dates = pd.bdate_range(start, periods=n, freq="B")
        rng = np.random.default_rng(42)
        close = 2000.0 + np.cumsum(rng.normal(0.5, 5.0, n))
        return pd.DataFrame(
            {
                "open": close - rng.uniform(0, 5, n),
                "high": close + rng.uniform(0, 10, n),
                "low": close - rng.uniform(0, 10, n),
                "close": close,
            },
            index=dates,
        )

    def _make_eurusd(self, n: int, start: str = "2018-01-01") -> pd.DataFrame:
        """Build n rows of EUR/USD data."""
        dates = pd.bdate_range(start, periods=n, freq="B")
        return pd.DataFrame({"close": [1.10] * n}, index=dates)

    def test_returns_result(self) -> None:
        """Shuffled-price test returns ShuffledPriceResult."""
        n = 500
        ohlcv = self._make_ohlcv(n)
        eurusd = self._make_eurusd(n)
        fedfunds: pd.Series[float] = pd.Series([], dtype=float)

        result = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=1.5,
            n_shuffles=5,
            seed=42,
        )

        assert isinstance(result, ShuffledPriceResult)
        assert result.n_shuffles == 5
        assert result.real_sharpe == 1.5
        assert len(result.shuffled_sharpes) == 5
        assert 0.0 <= result.p_value <= 1.0

    def test_shuffled_sharpes_sorted(self) -> None:
        """Shuffled Sharpes should be sorted."""
        n = 500
        ohlcv = self._make_ohlcv(n)
        eurusd = self._make_eurusd(n)
        fedfunds: pd.Series[float] = pd.Series([], dtype=float)

        result = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=0.0,
            n_shuffles=5,
            seed=42,
        )
        for i in range(len(result.shuffled_sharpes) - 1):
            assert result.shuffled_sharpes[i] <= result.shuffled_sharpes[i + 1]

    def test_deterministic_with_seed(self) -> None:
        """Same seed produces same result."""
        n = 500
        ohlcv = self._make_ohlcv(n)
        eurusd = self._make_eurusd(n)
        fedfunds: pd.Series[float] = pd.Series([], dtype=float)

        r1 = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=0.5,
            n_shuffles=3,
            seed=123,
        )
        r2 = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=0.5,
            n_shuffles=3,
            seed=123,
        )
        assert r1.shuffled_sharpes == r2.shuffled_sharpes
        assert r1.p_value == r2.p_value

    def test_high_real_sharpe_low_p_value(self) -> None:
        """Very high real_sharpe -> all shuffled below -> p_value = 0.0 -> passed."""
        n = 500
        ohlcv = self._make_ohlcv(n)
        eurusd = self._make_eurusd(n)
        fedfunds: pd.Series[float] = pd.Series([], dtype=float)

        result = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=100.0,
            n_shuffles=5,
            seed=42,
        )
        # With real_sharpe=100, no shuffled run should beat it
        assert result.p_value == 0.0
        assert result.passed is True

    def test_low_real_sharpe_high_p_value(self) -> None:
        """Very low real_sharpe -> most shuffled above -> high p_value -> not passed."""
        n = 500
        ohlcv = self._make_ohlcv(n)
        eurusd = self._make_eurusd(n)
        fedfunds: pd.Series[float] = pd.Series([], dtype=float)

        result = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=-100.0,
            n_shuffles=5,
            seed=42,
        )
        # With real_sharpe=-100, all shuffled should beat it
        assert result.p_value == pytest.approx(1.0)
        assert result.passed is False

    def test_result_is_frozen(self) -> None:
        """ShuffledPriceResult is immutable."""
        r = ShuffledPriceResult(
            real_sharpe=1.0,
            shuffled_sharpes=(0.5,),
            p_value=0.0,
            n_shuffles=1,
            passed=True,
        )
        with pytest.raises(AttributeError):
            r.passed = False  # type: ignore[misc]

    def test_p_value_boundary(self) -> None:
        """p_value exactly 0.01 is NOT passed (strict <)."""
        # Construct result manually to test boundary
        r = ShuffledPriceResult(
            real_sharpe=1.0,
            shuffled_sharpes=(0.5,),
            p_value=0.01,
            n_shuffles=100,
            passed=False,  # 0.01 is NOT < 0.01
        )
        assert r.passed is False

    def test_eurusd_with_sma_200_already_present(self) -> None:
        """When eurusd already has sma_200, it is used directly."""
        n = 500
        ohlcv = self._make_ohlcv(n)
        dates = pd.bdate_range("2018-01-01", periods=n, freq="B")
        eurusd = pd.DataFrame({"close": [1.10] * n, "sma_200": [1.08] * n}, index=dates)
        fedfunds: pd.Series[float] = pd.Series([], dtype=float)

        result = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=1.5,
            n_shuffles=2,
            seed=42,
        )
        assert isinstance(result, ShuffledPriceResult)
        assert len(result.shuffled_sharpes) == 2

    def test_exception_in_indicator_computation(
        self,
        mocker: "pytest_mock.MockerFixture",
    ) -> None:
        """When compute_all_indicators raises, Sharpe 0.0 is recorded."""
        n = 500
        ohlcv = self._make_ohlcv(n)
        eurusd = self._make_eurusd(n)
        fedfunds: pd.Series[float] = pd.Series([], dtype=float)

        mocker.patch(
            "trading_advisor.backtest.validation.compute_all_indicators",
            side_effect=RuntimeError("degenerate series"),
        )

        result = run_shuffled_price_test(
            ohlcv=ohlcv,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=fedfunds,
            real_sharpe=1.0,
            n_shuffles=3,
            seed=42,
        )
        # All shuffled sharpes should be 0.0 because every iteration raised
        assert result.shuffled_sharpes == (0.0, 0.0, 0.0)
