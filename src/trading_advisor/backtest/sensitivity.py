"""Parameter sensitivity analysis and guard ablation.

Runs the backtest with varied parameters (composite threshold, ATR multiplier,
TP clamp, momentum lookback, EMA periods, fill price) and with individual
guards disabled, collecting metrics for comparison.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from trading_advisor.backtest.engine import BacktestParams, run_backtest
from trading_advisor.backtest.report import compute_metrics
from trading_advisor.guards.base import Guard
from trading_advisor.indicators.composite import (
    compute_composite,
    rolling_zscore,
)
from trading_advisor.indicators.technical import (
    compute_all_indicators,
    compute_ema,
    compute_sma,
)


@dataclass(frozen=True)
class SensitivityResult:
    """Result of a single sensitivity test run.

    Attributes:
        param_name: Name of the parameter being varied.
        param_value: The specific value used in this run.
        metrics: Performance metrics from the backtest.
    """

    param_name: str
    param_value: str
    metrics: dict[str, float]


def _ensure_eurusd_sma(eurusd: pd.DataFrame) -> pd.DataFrame:
    """Add sma_200 column to eurusd if missing.

    Args:
        eurusd: EUR/USD DataFrame with at least a ``close`` column.

    Returns:
        EUR/USD DataFrame with ``sma_200`` column.
    """
    if "sma_200" in eurusd.columns:
        return eurusd
    result = eurusd.copy()
    result["sma_200"] = compute_sma(eurusd["close"], window=200)
    return result


def run_threshold_sensitivity(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
    thresholds: Sequence[float] | None = None,
) -> tuple[SensitivityResult, ...]:
    """Vary composite buy threshold from 1.0 to 2.5 in 0.25 steps.

    Uses BacktestParams.composite_buy_threshold to override the signal
    classification without recomputing indicators.

    Args:
        indicators: Pre-computed indicator DataFrame with composite column.
        eurusd: EUR/USD DataFrame.
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital.
        thresholds: Custom threshold values. Defaults to [1.0, 1.25, ..., 2.5].

    Returns:
        Tuple of SensitivityResult, one per threshold value.
    """
    if thresholds is None:
        thresholds = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]

    results: list[SensitivityResult] = []
    for t in thresholds:
        params = BacktestParams(composite_buy_threshold=t)
        bt_result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=guards,
            guards_enabled=guards_enabled,
            fedfunds=fedfunds,
            starting_capital=starting_capital,
            params=params,
        )
        metrics = compute_metrics(bt_result, fedfunds)
        results.append(
            SensitivityResult(
                param_name="composite_buy_threshold",
                param_value=str(t),
                metrics=metrics,
            )
        )
    return tuple(results)


def run_atr_multiplier_sensitivity(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
    multipliers: Sequence[float] | None = None,
) -> tuple[SensitivityResult, ...]:
    """Vary ATR multiplier for SL and trailing stop.

    Args:
        indicators: Pre-computed indicator DataFrame with composite column.
        eurusd: EUR/USD DataFrame.
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital.
        multipliers: Values to test. Defaults to [1.5, 2.0, 2.5, 3.0].

    Returns:
        Tuple of SensitivityResult, one per multiplier value.
    """
    if multipliers is None:
        multipliers = [1.5, 2.0, 2.5, 3.0]

    results: list[SensitivityResult] = []
    for m in multipliers:
        params = BacktestParams(atr_multiplier=m)
        bt_result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=guards,
            guards_enabled=guards_enabled,
            fedfunds=fedfunds,
            starting_capital=starting_capital,
            params=params,
        )
        metrics = compute_metrics(bt_result, fedfunds)
        results.append(
            SensitivityResult(
                param_name="atr_multiplier",
                param_value=str(m),
                metrics=metrics,
            )
        )
    return tuple(results)


def run_tp_sensitivity(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
    clamp_ranges: Sequence[tuple[float, float]] | None = None,
) -> tuple[SensitivityResult, ...]:
    """Vary TP multiplier clamp range.

    Args:
        indicators: Pre-computed indicator DataFrame with composite column.
        eurusd: EUR/USD DataFrame.
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital.
        clamp_ranges: (min, max) tuples. Defaults to:
            [(2.0, 3.5), (2.0, 4.5), (2.0, 5.0), (2.5, 4.0),
             (2.5, 4.5), (2.5, 5.0), (3.0, 4.5), (3.0, 5.0)].

    Returns:
        Tuple of SensitivityResult, one per clamp range.
    """
    if clamp_ranges is None:
        clamp_ranges = [
            (2.0, 3.5),
            (2.0, 4.5),
            (2.0, 5.0),
            (2.5, 4.0),
            (2.5, 4.5),
            (2.5, 5.0),
            (3.0, 4.5),
            (3.0, 5.0),
        ]

    results: list[SensitivityResult] = []
    for clamp_min, clamp_max in clamp_ranges:
        params = BacktestParams(tp_clamp_min=clamp_min, tp_clamp_max=clamp_max)
        bt_result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=guards,
            guards_enabled=guards_enabled,
            fedfunds=fedfunds,
            starting_capital=starting_capital,
            params=params,
        )
        metrics = compute_metrics(bt_result, fedfunds)
        results.append(
            SensitivityResult(
                param_name="tp_clamp",
                param_value=f"({clamp_min}, {clamp_max})",
                metrics=metrics,
            )
        )
    return tuple(results)


def run_momentum_lookback_sensitivity(
    ohlcv: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
    lookbacks: Sequence[int] | None = None,
) -> tuple[SensitivityResult, ...]:
    """Vary momentum lookback period (3M, 6M, 9M, 12M).

    This requires recomputing indicators and composite because the momentum
    component formula changes.

    Args:
        ohlcv: Raw OHLCV DataFrame (NOT pre-computed indicators).
        eurusd: EUR/USD DataFrame (may or may not have sma_200).
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital.
        lookbacks: Lookback periods in trading days. Defaults to [63, 126, 189, 252].

    Returns:
        Tuple of SensitivityResult, one per lookback value.
    """
    if lookbacks is None:
        lookbacks = [63, 126, 189, 252]

    eurusd_bt = _ensure_eurusd_sma(eurusd)

    results: list[SensitivityResult] = []
    for lookback in lookbacks:
        indicators = compute_all_indicators(ohlcv, eurusd)
        composite_df = compute_composite(indicators)

        # Override momentum_z with custom lookback
        momentum_raw: pd.Series[float] = (
            composite_df["close"].shift(21) / composite_df["close"].shift(lookback) - 1
        )
        composite_df["momentum_z"] = rolling_zscore(momentum_raw)

        # Recompute composite weighted sum
        composite_df["composite"] = (
            composite_df["momentum_z"] * 0.44
            + composite_df["trend_z"] * 0.22
            + composite_df["rsi_filter_z"] * 0.17
            + composite_df["atr_volatility_z"] * 0.11
            + composite_df["sr_proximity_z"] * 0.06
        )

        bt_result = run_backtest(
            indicators=composite_df,
            eurusd=eurusd_bt,
            guards=guards,
            guards_enabled=guards_enabled,
            fedfunds=fedfunds,
            starting_capital=starting_capital,
        )
        metrics = compute_metrics(bt_result, fedfunds)
        results.append(
            SensitivityResult(
                param_name="momentum_lookback",
                param_value=str(lookback),
                metrics=metrics,
            )
        )
    return tuple(results)


def run_ema_sensitivity(
    ohlcv: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
    ema_sets: Sequence[tuple[int, int, int]] | None = None,
) -> tuple[SensitivityResult, ...]:
    """Vary EMA periods (short, medium, long).

    This requires recomputing indicators because EMA values change,
    which affects the pullback zone guard (uses ema_8).

    Args:
        ohlcv: Raw OHLCV DataFrame.
        eurusd: EUR/USD DataFrame (may or may not have sma_200).
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital.
        ema_sets: (short, medium, long) tuples. Defaults to:
            [(8, 20, 50), (10, 21, 55), (12, 26, 50)].

    Returns:
        Tuple of SensitivityResult, one per EMA set.
    """
    if ema_sets is None:
        ema_sets = [(8, 20, 50), (10, 21, 55), (12, 26, 50)]

    eurusd_bt = _ensure_eurusd_sma(eurusd)

    results: list[SensitivityResult] = []
    for short, med, long_ in ema_sets:
        indicators = compute_all_indicators(ohlcv, eurusd)

        # Override EMA columns with new periods
        indicators["ema_8"] = compute_ema(ohlcv["close"], span=short)
        indicators["ema_20"] = compute_ema(ohlcv["close"], span=med)
        indicators["ema_50"] = compute_ema(ohlcv["close"], span=long_)

        # Update ema_fan
        indicators["ema_fan"] = (indicators["ema_8"] > indicators["ema_20"]) & (
            indicators["ema_20"] > indicators["ema_50"]
        )

        # Compute composite (composite is not affected by EMAs, but we need
        # the composite column for signal generation in the backtest)
        composite_df = compute_composite(indicators)

        bt_result = run_backtest(
            indicators=composite_df,
            eurusd=eurusd_bt,
            guards=guards,
            guards_enabled=guards_enabled,
            fedfunds=fedfunds,
            starting_capital=starting_capital,
        )
        metrics = compute_metrics(bt_result, fedfunds)
        results.append(
            SensitivityResult(
                param_name="ema_periods",
                param_value=f"({short}, {med}, {long_})",
                metrics=metrics,
            )
        )
    return tuple(results)


def run_fill_price_sensitivity(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
) -> tuple[SensitivityResult, ...]:
    """Test fill at buy_stop (default) vs midpoint.

    Args:
        indicators: Pre-computed indicator DataFrame.
        eurusd: EUR/USD DataFrame.
        guards: Guard instances.
        guards_enabled: Guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital.

    Returns:
        Tuple of 2 SensitivityResult: fill at buy_stop and fill at midpoint.
    """
    offsets = [0.0, 0.5]
    results: list[SensitivityResult] = []
    for offset in offsets:
        params = BacktestParams(fill_price_offset=offset)
        bt_result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=guards,
            guards_enabled=guards_enabled,
            fedfunds=fedfunds,
            starting_capital=starting_capital,
            params=params,
        )
        metrics = compute_metrics(bt_result, fedfunds)
        results.append(
            SensitivityResult(
                param_name="fill_price_offset",
                param_value=str(offset),
                metrics=metrics,
            )
        )
    return tuple(results)


def run_guard_ablation(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    fedfunds: "pd.Series[float]",
    starting_capital: float = 15000.0,
) -> tuple[SensitivityResult, ...]:
    """Disable each guard individually and compare metrics vs baseline.

    Runs: baseline (all enabled), then one run per guard with that guard disabled.

    Args:
        indicators: Pre-computed indicator DataFrame.
        eurusd: EUR/USD DataFrame.
        guards: All guard instances.
        guards_enabled: Baseline guard enable flags.
        fedfunds: FEDFUNDS rate series.
        starting_capital: Initial capital.

    Returns:
        Tuple of SensitivityResult: first is baseline, rest are per-guard ablations.
    """
    results: list[SensitivityResult] = []

    # Baseline: all guards as configured
    bt_result = run_backtest(
        indicators=indicators,
        eurusd=eurusd,
        guards=guards,
        guards_enabled=guards_enabled,
        fedfunds=fedfunds,
        starting_capital=starting_capital,
    )
    metrics = compute_metrics(bt_result, fedfunds)
    results.append(
        SensitivityResult(
            param_name="guard_ablation",
            param_value="baseline",
            metrics=metrics,
        )
    )

    # Ablate each guard
    for guard_name in guards_enabled:
        ablated = dict(guards_enabled)
        ablated[guard_name] = False
        bt_result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=guards,
            guards_enabled=ablated,
            fedfunds=fedfunds,
            starting_capital=starting_capital,
        )
        metrics = compute_metrics(bt_result, fedfunds)
        results.append(
            SensitivityResult(
                param_name="guard_ablation",
                param_value=f"without_{guard_name}",
                metrics=metrics,
            )
        )

    return tuple(results)
