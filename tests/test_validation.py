"""Tests for OHLCV validation logic."""

import pandas as pd
import pytest

from trading_advisor.data.validation import validate_ohlcv


def test_valid_data_passes(sample_ohlcv: pd.DataFrame) -> None:
    """Valid baseline data returns valid=True with no errors or warnings."""
    result = validate_ohlcv(sample_ohlcv)
    assert result.valid is True
    assert result.errors == []
    assert result.warnings == []


def test_high_less_than_low_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """A row where high < low produces an error."""
    df = sample_ohlcv.copy()
    df.iloc[2, df.columns.get_loc("high")] = 1980.0  # high < low (1992)
    result = validate_ohlcv(df)
    assert result.valid is False
    assert any("high >= low" in e for e in result.errors)


def test_null_in_close_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """A null value in the close column produces an error."""
    df = sample_ohlcv.copy()
    df.iloc[3, df.columns.get_loc("close")] = float("nan")
    result = validate_ohlcv(df)
    assert result.valid is False
    assert any("null" in e.lower() for e in result.errors)


def test_duplicate_timestamps_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """Duplicate index timestamps produce an error."""
    # Concatenate the first row to the full DataFrame to create a duplicate timestamp.
    dup_df = pd.concat([sample_ohlcv.iloc[:1], sample_ohlcv])
    result = validate_ohlcv(dup_df)
    assert result.valid is False
    assert any("duplicate" in e.lower() for e in result.errors)


def test_non_monotonic_index_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """A non-monotonically-increasing index produces an error."""
    df = sample_ohlcv.copy()
    # Swap first two rows to break monotonicity
    idx = list(df.index)
    idx[0], idx[1] = idx[1], idx[0]
    df.index = pd.DatetimeIndex(idx)
    result = validate_ohlcv(df)
    assert result.valid is False
    assert any("monoton" in e.lower() for e in result.errors)


def test_large_price_jump_gives_warning(sample_ohlcv: pd.DataFrame) -> None:
    """A 6% close-to-close jump produces a warning but valid=True."""
    df = sample_ohlcv.copy()
    close_prev = df.iloc[4]["close"]
    new_close = close_prev * 1.06 + 1.0
    # Keep high >= new_close so no price-relationship error is triggered.
    df.iloc[5, df.columns.get_loc("close")] = new_close
    df.iloc[5, df.columns.get_loc("high")] = new_close + 10.0
    result = validate_ohlcv(df)
    assert result.valid is True
    assert result.errors == []
    assert len(result.warnings) >= 1
    assert any(
        "price" in w.lower() or "jump" in w.lower() or "anomaly" in w.lower()
        for w in result.warnings
    )


def test_empty_dataframe_raises_value_error() -> None:
    """An empty DataFrame raises ValueError immediately."""
    df = pd.DataFrame()
    with pytest.raises(ValueError, match="empty"):
        validate_ohlcv(df)


def test_missing_required_column_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """A DataFrame missing the 'high' column produces an error."""
    df = sample_ohlcv.drop(columns=["high"])
    result = validate_ohlcv(df)
    assert result.valid is False
    assert any("high" in e.lower() for e in result.errors)


def test_high_less_than_open_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """A row where high < open produces an error."""
    df = sample_ohlcv.copy()
    # open[0] = 2000.0, set high[0] = 1999.0
    df.iloc[0, df.columns.get_loc("high")] = 1999.0
    result = validate_ohlcv(df)
    assert result.valid is False
    assert any("high >= open" in e for e in result.errors)


def test_low_greater_than_close_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """A row where low > close produces an error."""
    df = sample_ohlcv.copy()
    # close[0] = 2005.0, set low[0] = 2010.0
    df.iloc[0, df.columns.get_loc("low")] = 2010.0
    result = validate_ohlcv(df)
    assert result.valid is False
    assert any("low <= close" in e for e in result.errors)


def test_non_datetime_index_gives_error(sample_ohlcv: pd.DataFrame) -> None:
    """A DataFrame whose index is not a DatetimeIndex produces an error."""
    df = sample_ohlcv.reset_index(drop=True)  # integer index
    result = validate_ohlcv(df)
    assert result.valid is False
    assert any("datetimeindex" in e.lower() for e in result.errors)


def test_multiple_errors_collected(sample_ohlcv: pd.DataFrame) -> None:
    """Multiple independent violations are all collected in a single run."""
    df = sample_ohlcv.copy()
    # Introduce high < low on row 0 (high[0]=2010, set it to 1985 < low[0]=1990)
    df.iloc[0, df.columns.get_loc("high")] = 1985.0
    # Introduce low > close on row 1 (close[1]=2006, set low to 2020)
    df.iloc[1, df.columns.get_loc("low")] = 2020.0
    result = validate_ohlcv(df)
    assert result.valid is False
    assert len(result.errors) >= 2


def test_zero_prev_close_does_not_raise(sample_ohlcv: pd.DataFrame) -> None:
    """A zero prev_close is masked out and does not generate a spurious inf warning."""
    df = sample_ohlcv.copy()
    # Set close on row 0 to zero; row 1's pct_change uses row 0 as prev_close
    df.iloc[0, df.columns.get_loc("close")] = 0.0
    # Also fix open/high/low to satisfy OHLC constraints with close=0
    df.iloc[0, df.columns.get_loc("open")] = 0.0
    df.iloc[0, df.columns.get_loc("high")] = 0.0
    df.iloc[0, df.columns.get_loc("low")] = 0.0
    result = validate_ohlcv(df)
    # Must not raise; the zero-prev-close row must be masked, not produce inf warnings
    assert isinstance(result.valid, bool)
    # No warning should contain "inf" or represent a division-by-zero artifact
    for w in result.warnings:
        assert "inf" not in w.lower()
