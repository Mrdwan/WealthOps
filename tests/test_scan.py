"""Tests for historical signal scanner."""

import pandas as pd
import pytest

from trading_advisor.guards.base import Guard, GuardResult
from trading_advisor.strategy.scan import scan_signals


class _StubGuard(Guard):
    """Stub guard that always passes or fails based on constructor arg."""

    def __init__(self, name: str, passes: bool = True) -> None:
        self._name = name
        self._passes = passes

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, **kwargs: object) -> GuardResult:
        return GuardResult(
            passed=self._passes,
            guard_name=self._name,
            reason="stub" if self._passes else "blocked",
        )


def _make_multi_day_indicators(
    dates: pd.DatetimeIndex,
    signals: list[str],
    composites: list[float],
) -> pd.DataFrame:
    """Build a multi-row indicators DataFrame for testing.

    Args:
        dates: DatetimeIndex for the rows.
        signals: Signal string per row.
        composites: Composite score per row.

    Returns:
        DataFrame with required indicator columns.
    """
    return pd.DataFrame(
        {
            "signal": signals,
            "composite": composites,
            "high": [2050.0] * len(dates),
            "close": [2045.0] * len(dates),
            "atr_14": [30.0] * len(dates),
            "adx_14": [25.0] * len(dates),
            "ema_8": [2044.0] * len(dates),
        },
        index=dates,
    )


def _make_multi_day_eurusd(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Build a multi-row EUR/USD DataFrame for testing.

    Args:
        dates: DatetimeIndex for the rows.

    Returns:
        DataFrame with close and sma_200 columns.
    """
    return pd.DataFrame(
        {
            "close": [1.08] * len(dates),
            "sma_200": [1.05] * len(dates),
        },
        index=dates,
    )


# Pre-computed expected values (high=2050, atr=30, adx=25, equity=15000):
# buy_stop = 2050.0 + 0.02*30 = 2050.6
# limit    = 2050.6 + 0.05*30 = 2052.1
# SL       = 2050.6 - 2*30    = 1990.6
# TP mult  = max(2.5, min(4.5, 2 + 25/30)) = 2.8333...
# TP       = 2050.6 + 2.8333*30 = 2135.6
# size     = min(atr_based=5.0, cap_based=1.09724) -> floor -> 1.09
# risk_amount = 1.09 * 60 = 65.4
# risk_reward = 85.0 / 60.0 = 1.4166...

_BUY_STOP = 2050.6
_LIMIT = 2052.1
_STOP_LOSS = 1990.6
_TAKE_PROFIT = 2135.6
_SIZE = 1.09
_RISK_AMOUNT = 65.4
_RISK_REWARD = 85.0 / 60.0


class TestScanSignals:
    """Tests for scan_signals diagnostic function."""

    def test_finds_buy_signals(self) -> None:
        """BUY and STRONG_BUY rows are captured; NEUTRAL rows are ignored."""
        dates = pd.bdate_range("2024-01-01", periods=5)
        signals = ["NEUTRAL", "BUY", "NEUTRAL", "STRONG_BUY", "NEUTRAL"]
        composites = [0.5, 1.75, 0.3, 2.5, -0.1]

        indicators = _make_multi_day_indicators(dates, signals, composites)
        eurusd = _make_multi_day_eurusd(dates)
        guards = [_StubGuard("MacroGate"), _StubGuard("TrendGate")]
        enabled: dict[str, bool] = {"MacroGate": True, "TrendGate": True}

        result = scan_signals(indicators, eurusd, guards, enabled)

        assert len(result) == 2

        # Verify output columns present
        expected_cols = {
            "date",
            "composite",
            "signal",
            "buy_stop",
            "limit",
            "stop_loss",
            "take_profit",
            "position_size",
            "risk_amount",
            "risk_reward",
        }
        assert set(result.columns) == expected_cols

        # Verify dates[1] and dates[3] were captured
        result_dates = list(result["date"])
        assert result_dates[0] == dates[1].date()
        assert result_dates[1] == dates[3].date()

        # Verify computed values in first row
        row = result.iloc[0]
        assert row["buy_stop"] == pytest.approx(_BUY_STOP)
        assert row["stop_loss"] == pytest.approx(_STOP_LOSS)
        assert row["take_profit"] == pytest.approx(_TAKE_PROFIT, rel=1e-4)
        assert row["position_size"] == pytest.approx(_SIZE)
        assert row["limit"] == pytest.approx(_LIMIT)
        assert row["risk_amount"] == pytest.approx(_RISK_AMOUNT)
        assert row["risk_reward"] == pytest.approx(_RISK_REWARD)

    def test_empty_when_no_signals(self) -> None:
        """All NEUTRAL signals produce an empty DataFrame with correct columns."""
        dates = pd.bdate_range("2024-01-01", periods=3)
        signals = ["NEUTRAL", "NEUTRAL", "NEUTRAL"]
        composites = [0.1, 0.2, 0.3]

        indicators = _make_multi_day_indicators(dates, signals, composites)
        eurusd = _make_multi_day_eurusd(dates)
        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        result = scan_signals(indicators, eurusd, guards, enabled)

        assert result.empty
        expected_cols = [
            "date",
            "composite",
            "signal",
            "buy_stop",
            "limit",
            "stop_loss",
            "take_profit",
            "position_size",
            "risk_amount",
            "risk_reward",
        ]
        assert list(result.columns) == expected_cols

    def test_guard_failure_filters(self) -> None:
        """A guard that always fails blocks all signals, returning empty DataFrame."""
        dates = pd.bdate_range("2024-01-01", periods=3)
        signals = ["BUY", "BUY", "BUY"]
        composites = [1.75, 1.8, 1.9]

        indicators = _make_multi_day_indicators(dates, signals, composites)
        eurusd = _make_multi_day_eurusd(dates)
        guards = [_StubGuard("AlwaysFail", passes=False)]
        enabled: dict[str, bool] = {"AlwaysFail": True}

        result = scan_signals(indicators, eurusd, guards, enabled)

        assert result.empty

    def test_no_lookahead(self) -> None:
        """Signal at dates[2] only — output row date matches dates[2] exactly."""
        dates = pd.bdate_range("2024-01-01", periods=5)
        signals = ["NEUTRAL", "NEUTRAL", "BUY", "NEUTRAL", "NEUTRAL"]
        composites = [0.1, 0.2, 1.75, 0.3, 0.4]

        indicators = _make_multi_day_indicators(dates, signals, composites)
        eurusd = _make_multi_day_eurusd(dates)
        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        result = scan_signals(indicators, eurusd, guards, enabled)

        assert len(result) == 1
        assert result.iloc[0]["date"] == dates[2].date()

    def test_output_columns(self) -> None:
        """Output DataFrame has exactly the required columns."""
        dates = pd.bdate_range("2024-01-01", periods=2)
        signals = ["BUY", "NEUTRAL"]
        composites = [1.75, 0.3]

        indicators = _make_multi_day_indicators(dates, signals, composites)
        eurusd = _make_multi_day_eurusd(dates)
        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        result = scan_signals(indicators, eurusd, guards, enabled)

        expected_cols = [
            "date",
            "composite",
            "signal",
            "buy_stop",
            "limit",
            "stop_loss",
            "take_profit",
            "position_size",
            "risk_amount",
            "risk_reward",
        ]
        assert list(result.columns) == expected_cols

    def test_zero_size_skipped(self) -> None:
        """Signal is skipped when computed position size is zero (equity too low)."""
        dates = pd.bdate_range("2024-01-01", periods=2)
        signals = ["BUY", "NEUTRAL"]
        composites = [1.75, 0.3]

        indicators = _make_multi_day_indicators(dates, signals, composites)
        eurusd = _make_multi_day_eurusd(dates)
        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        # With equity=50, size rounds down to 0.0 (below 0.01 minimum lot)
        result = scan_signals(indicators, eurusd, guards, enabled, starting_equity=50.0)

        assert result.empty

    def test_missing_eurusd_date_skipped(self) -> None:
        """Signal on dates[1] is skipped when EUR/USD data is absent for that date."""
        dates = pd.bdate_range("2024-01-01", periods=3)
        signals = ["NEUTRAL", "BUY", "NEUTRAL"]
        composites = [0.1, 1.75, 0.2]

        indicators = _make_multi_day_indicators(dates, signals, composites)

        # EUR/USD only has dates[0] and dates[2] — dates[1] is missing
        eurusd_dates = pd.DatetimeIndex([dates[0], dates[2]])
        eurusd = _make_multi_day_eurusd(eurusd_dates)

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        result = scan_signals(indicators, eurusd, guards, enabled)

        assert result.empty
