"""Statistical validation: walk-forward analysis and walk-forward efficiency.

Walk-forward uses expanding windows: 3-year train, 6-month test, 6-month roll.
WFE = mean(OOS Sharpe) / mean(in-sample Sharpe). Pass > 50%.
"""

import datetime
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from trading_advisor.backtest.engine import BacktestParams, run_backtest
from trading_advisor.backtest.report import compute_metrics
from trading_advisor.guards.base import Guard


@dataclass(frozen=True)
class WalkForwardWindow:
    """A single walk-forward analysis window.

    Attributes:
        train_start: First date of the training period.
        train_end: Last date of the training period.
        test_start: First date of the test (OOS) period.
        test_end: Last date of the test (OOS) period.
    """

    train_start: datetime.date
    train_end: datetime.date
    test_start: datetime.date
    test_end: datetime.date


@dataclass(frozen=True)
class WalkForwardResult:
    """Result of a complete walk-forward analysis.

    Attributes:
        windows: The windows used.
        in_sample_sharpes: Sharpe ratio for each training window.
        oos_sharpes: Sharpe ratio for each test window.
        wfe: Walk-forward efficiency (mean OOS / mean IS).
    """

    windows: tuple[WalkForwardWindow, ...]
    in_sample_sharpes: tuple[float, ...]
    oos_sharpes: tuple[float, ...]
    wfe: float


def generate_walk_forward_windows(
    start_date: datetime.date,
    end_date: datetime.date,
    train_years: int = 3,
    test_months: int = 6,
    step_months: int = 6,
) -> tuple[WalkForwardWindow, ...]:
    """Generate expanding walk-forward analysis windows.

    Each window has a training period starting from start_date and expanding
    by step_months each iteration, followed by a fixed-length test period.

    Args:
        start_date: First available data date.
        end_date: Last available data date.
        train_years: Initial training period in years.
        test_months: Test (OOS) period length in months.
        step_months: Step size between windows in months.

    Returns:
        Tuple of WalkForwardWindow instances.

    Raises:
        ValueError: If date range is too short for even one window.
    """
    windows: list[WalkForwardWindow] = []

    ts_start = pd.Timestamp(start_date)
    ts_end = pd.Timestamp(end_date)

    train_end_ts = ts_start + pd.DateOffset(years=train_years)

    while True:
        test_start_ts = train_end_ts
        test_end_ts = test_start_ts + pd.DateOffset(months=test_months)

        if test_end_ts > ts_end:
            break

        windows.append(
            WalkForwardWindow(
                train_start=ts_start.date(),
                train_end=(train_end_ts - pd.DateOffset(days=1)).date(),
                test_start=train_end_ts.date(),
                test_end=(test_end_ts - pd.DateOffset(days=1)).date(),
            )
        )

        train_end_ts = train_end_ts + pd.DateOffset(months=step_months)

    if not windows:
        raise ValueError(
            f"Date range {start_date} to {end_date} too short for "
            f"{train_years}yr train + {test_months}mo test"
        )

    return tuple(windows)


def _run_window_backtest(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    start: datetime.date,
    end: datetime.date,
    starting_capital: float,
    params: BacktestParams | None,
) -> float:
    """Run backtest on a date slice and return its Sharpe ratio.

    Slices the indicators DataFrame to [start, end] (inclusive) and runs
    the backtest. Returns the Sharpe ratio from compute_metrics.

    Args:
        indicators: Full indicator DataFrame.
        eurusd: Full EUR/USD DataFrame.
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        start: First date (inclusive).
        end: Last date (inclusive).
        starting_capital: Initial capital.
        params: Optional BacktestParams overrides.

    Returns:
        Sharpe ratio for the window. Returns 0.0 if no trading days.
    """
    ts_start = pd.Timestamp(start)
    ts_end = pd.Timestamp(end)

    mask = (indicators.index >= ts_start) & (indicators.index <= ts_end)
    window_indicators = indicators.loc[mask]

    if window_indicators.empty:
        return 0.0

    eurusd_mask = (eurusd.index >= ts_start) & (eurusd.index <= ts_end)
    window_eurusd = eurusd.loc[eurusd_mask]

    result = run_backtest(
        indicators=window_indicators,
        eurusd=window_eurusd,
        guards=guards,
        guards_enabled=guards_enabled,
        fedfunds=fedfunds,
        starting_capital=starting_capital,
        params=params,
    )

    metrics = compute_metrics(result, fedfunds)
    return metrics["sharpe_ratio"]


def compute_wfe(
    in_sample_sharpes: Sequence[float],
    oos_sharpes: Sequence[float],
) -> float:
    """Compute Walk-Forward Efficiency.

    WFE = mean(OOS Sharpe) / mean(in-sample Sharpe).
    Returns 0.0 if mean IS Sharpe is zero or negative (avoids division
    by zero and meaningless ratios).

    Args:
        in_sample_sharpes: Sharpe ratios from training windows.
        oos_sharpes: Sharpe ratios from test windows.

    Returns:
        WFE as a fraction (e.g. 0.6 = 60%). Pass threshold is > 0.5.
    """
    if not in_sample_sharpes or not oos_sharpes:
        return 0.0

    mean_is = sum(in_sample_sharpes) / len(in_sample_sharpes)
    mean_oos = sum(oos_sharpes) / len(oos_sharpes)

    if mean_is <= 0.0:
        return 0.0

    return mean_oos / mean_is


def run_walk_forward(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
    train_years: int = 3,
    test_months: int = 6,
    step_months: int = 6,
    params: BacktestParams | None = None,
) -> WalkForwardResult:
    """Run a complete walk-forward analysis.

    Generates expanding windows, runs backtest on each training and test
    period, computes Sharpe ratios, and calculates WFE.

    Args:
        indicators: Full indicator DataFrame with DatetimeIndex.
        eurusd: Full EUR/USD DataFrame with DatetimeIndex.
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital for each window.
        train_years: Initial training period in years.
        test_months: Test period length in months.
        step_months: Step between windows in months.
        params: Optional BacktestParams overrides.

    Returns:
        WalkForwardResult with per-window Sharpes and WFE.
    """
    dates = sorted(indicators.index)
    start_date = pd.Timestamp(dates[0]).date()
    end_date = pd.Timestamp(dates[-1]).date()

    windows = generate_walk_forward_windows(
        start_date, end_date, train_years, test_months, step_months
    )

    is_sharpes: list[float] = []
    oos_sharpes: list[float] = []

    for w in windows:
        is_sharpe = _run_window_backtest(
            indicators,
            eurusd,
            guards,
            guards_enabled,
            fedfunds,
            w.train_start,
            w.train_end,
            starting_capital,
            params,
        )
        oos_sharpe = _run_window_backtest(
            indicators,
            eurusd,
            guards,
            guards_enabled,
            fedfunds,
            w.test_start,
            w.test_end,
            starting_capital,
            params,
        )
        is_sharpes.append(is_sharpe)
        oos_sharpes.append(oos_sharpe)

    wfe = compute_wfe(is_sharpes, oos_sharpes)

    return WalkForwardResult(
        windows=windows,
        in_sample_sharpes=tuple(is_sharpes),
        oos_sharpes=tuple(oos_sharpes),
        wfe=wfe,
    )


@dataclass(frozen=True)
class MonteCarloResult:
    """Result of a Monte Carlo bootstrap simulation.

    Attributes:
        terminal_equities: Sorted tuple of terminal equity values from resamples.
        percentile_5: 5th percentile of terminal equity distribution.
        starting_capital: The starting capital used.
        n_resamples: Number of resamples performed.
        passed: True if 5th percentile > starting capital.
    """

    terminal_equities: tuple[float, ...]
    percentile_5: float
    starting_capital: float
    n_resamples: int
    passed: bool


def run_monte_carlo(
    trade_pnls: Sequence[float],
    starting_capital: float,
    n_resamples: int = 10000,
    seed: int | None = None,
) -> MonteCarloResult:
    """Run Monte Carlo bootstrap on trade P&Ls.

    Resamples trade P&Ls with replacement, accumulates them to build
    simulated equity paths, and reports the terminal equity distribution.

    Algorithm:
        For each resample:
            1. Draw len(trade_pnls) P&Ls with replacement
            2. Terminal equity = starting_capital + sum(drawn P&Ls)
        Sort terminal equities, compute 5th percentile.

    Args:
        trade_pnls: Sequence of trade P&L values from the backtest.
        starting_capital: Initial capital.
        n_resamples: Number of resamples (default 10,000).
        seed: Optional RNG seed for reproducibility.

    Returns:
        MonteCarloResult with distribution and pass/fail.

    Raises:
        ValueError: If trade_pnls is empty.
    """
    if not trade_pnls:
        raise ValueError("trade_pnls is empty; cannot run Monte Carlo bootstrap")

    pnls_array = np.array(trade_pnls, dtype=float)
    n_trades = len(pnls_array)

    rng = np.random.default_rng(seed)
    draws = rng.choice(pnls_array, size=(n_resamples, n_trades), replace=True)
    row_sums = draws.sum(axis=1)
    equities = starting_capital + row_sums

    sorted_equities = np.sort(equities)
    percentile_5 = float(np.percentile(sorted_equities, 5))
    passed = percentile_5 > starting_capital

    return MonteCarloResult(
        terminal_equities=tuple(float(v) for v in sorted_equities),
        percentile_5=percentile_5,
        starting_capital=starting_capital,
        n_resamples=n_resamples,
        passed=passed,
    )


def compute_t_statistic(trade_pnls: Sequence[float]) -> float:
    """Compute the t-statistic of trade returns.

    Formula: t = mean(pnls) * sqrt(N) / std(pnls)
    Tests whether the mean trade return is significantly different from zero.
    Pass threshold: t > 2.0.

    Args:
        trade_pnls: Sequence of trade P&L values.

    Returns:
        t-statistic value. Returns 0.0 if fewer than 2 trades or zero std.
    """
    if len(trade_pnls) < 2:
        return 0.0

    pnls_array = np.array(trade_pnls, dtype=float)
    mean = float(np.mean(pnls_array))
    std = float(np.std(pnls_array, ddof=1))

    if std == 0.0:
        return 0.0

    return mean * math.sqrt(len(trade_pnls)) / std
