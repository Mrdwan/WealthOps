"""Technical indicators and momentum composite for XAU/USD.

Public API:
    - ``compute_all_indicators``: assembly of all technical features.
    - ``compute_composite``: momentum composite with signal classification.
    - Individual indicators for direct use.
"""

from trading_advisor.indicators.composite import (
    Signal,
    classify_signal,
    compute_composite,
)
from trading_advisor.indicators.technical import (
    compute_adx,
    compute_all_indicators,
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

__all__ = [
    "Signal",
    "classify_signal",
    "compute_composite",
    "compute_adx",
    "compute_all_indicators",
    "compute_atr",
    "compute_distance_from_20d_low",
    "compute_ema",
    "compute_ema_fan",
    "compute_macd_histogram",
    "compute_relative_strength_vs_usd",
    "compute_rsi",
    "compute_sma",
    "compute_wick_ratios",
]
