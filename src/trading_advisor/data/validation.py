"""OHLCV DataFrame validation utilities.

Provides :func:`validate_ohlcv` which inspects a DataFrame for structural and
logical integrity before it is consumed by strategy code.
"""

from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS: list[str] = ["open", "high", "low", "close"]
_PRICE_JUMP_THRESHOLD: float = 0.05


@dataclass(frozen=True)
class ValidationResult:
    """Immutable result of an OHLCV validation run.

    Attributes:
        valid: True when no hard errors were found; data is usable.
        errors: Hard failures — data is unusable when this list is non-empty.
        warnings: Anomalies to log; data is still usable.
    """

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_ohlcv(df: pd.DataFrame) -> ValidationResult:
    """Validate an OHLCV DataFrame against structural and logical rules.

    Rules applied (in order):
    - DataFrame must not be empty (raises immediately).
    - Required columns ``open``, ``high``, ``low``, ``close`` must be present.
    - No null values in OHLC columns.
    - ``high >= low`` for every row.
    - ``high >= open`` and ``high >= close`` for every row.
    - ``low <= open`` and ``low <= close`` for every row.
    - Index must be a :class:`pandas.DatetimeIndex`, monotonically increasing.
    - No duplicate timestamps.
    - Close-to-close jumps > 5% are recorded as warnings (data still usable).

    Args:
        df: DataFrame to validate.  Expected index is a DatetimeIndex with
            columns including at minimum ``open``, ``high``, ``low``, ``close``.

    Returns:
        :class:`ValidationResult` with ``valid=True`` when no errors were found.

    Raises:
        ValueError: If *df* is empty (zero rows **and** zero columns, or zero
            rows after the index check).
    """
    if df.empty:
        raise ValueError("DataFrame is empty — nothing to validate.")

    errors: list[str] = []
    warnings: list[str] = []

    # 1. Required columns present
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
        # Without required columns we cannot run price checks; return early.
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # 2. No nulls in OHLC columns
    null_cols = [col for col in REQUIRED_COLUMNS if df[col].isnull().any()]
    if null_cols:
        errors.append(f"Null values found in columns: {null_cols}")

    # 3–6. Price relationship checks (only meaningful when no nulls)
    if not null_cols:
        bad_hl = df[df["high"] < df["low"]]
        if not bad_hl.empty:
            errors.append(
                f"high >= low violated on {len(bad_hl)} row(s): index={list(bad_hl.index)}"
            )

        bad_ho = df[df["high"] < df["open"]]
        if not bad_ho.empty:
            errors.append(
                f"high >= open violated on {len(bad_ho)} row(s): index={list(bad_ho.index)}"
            )

        bad_hc = df[df["high"] < df["close"]]
        if not bad_hc.empty:
            errors.append(
                f"high >= close violated on {len(bad_hc)} row(s): index={list(bad_hc.index)}"
            )

        bad_lo = df[df["low"] > df["open"]]
        if not bad_lo.empty:
            errors.append(
                f"low <= open violated on {len(bad_lo)} row(s): index={list(bad_lo.index)}"
            )

        bad_lc = df[df["low"] > df["close"]]
        if not bad_lc.empty:
            errors.append(
                f"low <= close violated on {len(bad_lc)} row(s): index={list(bad_lc.index)}"
            )

    # 7. Index must be DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        errors.append(f"Index must be a DatetimeIndex, got {type(df.index).__name__!r} instead.")
    else:
        # 7b. Monotonically increasing
        if not df.index.is_monotonic_increasing:
            errors.append("Index is not monotonically increasing.")

        # 8. No duplicate timestamps
        if df.index.duplicated().any():
            dup_count = int(df.index.duplicated().sum())
            errors.append(f"Duplicate timestamps found: {dup_count} duplicate(s).")

    # 9. Price-jump warnings (close-to-close > 5%)
    if not null_cols and len(df) > 1:
        close = df["close"]
        prev_close = close.shift(1)
        nonzero_mask = prev_close != 0
        pct_change = pd.Series(dtype=float, index=close.index)
        pct_change[nonzero_mask] = (
            close[nonzero_mask] - prev_close[nonzero_mask]
        ).abs() / prev_close[nonzero_mask]
        jumps = pct_change[pct_change > _PRICE_JUMP_THRESHOLD].dropna()
        for ts, pct in jumps.items():
            warnings.append(f"Price anomaly: close-to-close jump of {pct:.1%} at {ts}.")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
