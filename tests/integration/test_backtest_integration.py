"""Integration tests: full backtest pipeline end-to-end.

Tests run_backtest -> compute_metrics -> generate_report with synthetic
data and known outcomes. Each scenario verifies trade count, entry/exit
prices, exit reasons, P&L consistency, and equity curve shape.
"""

from __future__ import annotations

import pandas as pd
import pytest

from trading_advisor.backtest.engine import BacktestResult, ExitReason, run_backtest
from trading_advisor.backtest.report import compute_metrics, generate_report

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_IG_ADMIN_FEE: float = 0.025


def _build_scenario(
    n: int,
    overrides: dict[str, list[float | str]] | None = None,
    starting_capital: float = 100_000.0,
    spread: float = 0.0,
    slippage: float = 0.0,
) -> BacktestResult:
    """Run backtest on synthetic data with per-index overrides.

    Args:
        n: Number of business days.
        overrides: Column name -> list of (index, value) style values.
            The list length can be <= n; only positions with explicit
            values are overridden.
        starting_capital: Initial account balance.
        spread: Spread per side in points.
        slippage: Slippage per side in points.

    Returns:
        BacktestResult from the engine.
    """
    dates = pd.bdate_range("2024-01-01", periods=n, freq="B")
    defaults: dict[str, list[float | str]] = {
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
    if overrides:
        for key, vals in overrides.items():
            for i, val in enumerate(vals):
                defaults[key][i] = val

    indicators = pd.DataFrame(defaults, index=dates)
    eurusd = pd.DataFrame({"close": [1.10] * n, "sma_200": [1.08] * n}, index=dates)
    fedfunds = pd.Series([], dtype=float)

    return run_backtest(
        indicators,
        eurusd,
        [],
        {},
        fedfunds,
        starting_capital=starting_capital,
        spread_per_side=spread,
        slippage_per_side=slippage,
    )


def _nightly_funding(entry_price: float, size: float) -> float:
    """Compute one night's funding with zero fedfunds (admin fee only).

    Args:
        entry_price: Entry price for the position.
        size: Current position size in lots.

    Returns:
        Funding charge for one night.
    """
    return entry_price * size * _IG_ADMIN_FEE / 365


def _assert_equity_consistent(
    result: BacktestResult,
    starting_capital: float,
) -> None:
    """Assert final equity = starting_capital + sum(trade.pnl).

    Only valid when no position is open at the end.

    Args:
        result: Completed backtest result.
        starting_capital: Initial capital.
    """
    expected = starting_capital + sum(t.pnl for t in result.trades)
    actual = float(result.equity_curve["equity"].iloc[-1])
    assert actual == pytest.approx(expected, abs=0.01)


# ------------------------------------------------------------------
# Scenario A: TP hit, then trailing stop
# ------------------------------------------------------------------


class TestScenarioA:
    """Full lifecycle: BUY -> fill -> TP 50% close -> trailing stop exit."""

    def test_trade_count_and_reasons(self) -> None:
        """Two trades: first TP, second trailing stop."""
        result = self._run()
        assert len(result.trades) == 2
        assert result.trades[0].exit_reason == ExitReason.TAKE_PROFIT
        assert result.trades[1].exit_reason == ExitReason.TRAILING_STOP

    def test_entry_exit_prices(self) -> None:
        """Entry at buy_stop=2001, TP at 2151, trailing at 2080."""
        result = self._run()
        t1, t2 = result.trades

        assert t1.entry_price == 2001.0
        assert t1.exit_price == 2151.0
        assert t2.entry_price == 2001.0
        assert t2.exit_price == 2080.0

    def test_trade_sizes(self) -> None:
        """TP closes half (3.74), trailing closes remainder (3.75)."""
        result = self._run()
        t1, t2 = result.trades

        # half = floor(7.49 / 2 * 100) / 100 = floor(374.5) / 100 = 3.74
        assert t1.size == 3.74
        # remainder = 7.49 - 3.74 = 3.75
        assert t2.size == 3.75

    def test_pnl_with_funding(self) -> None:
        """P&L accounts for raw gain minus admin-fee funding."""
        result = self._run()
        t1, t2 = result.trades

        entry = 2001.0
        full_size = 7.49
        half_size = 3.74
        remaining_size = 3.75

        nf = _nightly_funding(entry, full_size)  # nightly at full size
        nr = _nightly_funding(entry, remaining_size)  # nightly at remaining

        # 6 nights before TP (days_held 1-6, one night per day)
        # TP triggers on days_held=7 (day 10, index 9)
        cum_at_tp = 6 * nf
        funding_t1 = cum_at_tp * (half_size / full_size)

        raw_pnl_t1 = (2151.0 - entry) * half_size  # 150 * 3.74 = 561.0
        assert raw_pnl_t1 == 561.0
        net_pnl_t1 = raw_pnl_t1 - funding_t1
        assert t1.pnl == pytest.approx(net_pnl_t1, rel=1e-6)
        assert t1.funding_cost == pytest.approx(funding_t1, rel=1e-6)

        # After TP: cum = cum_at_tp * (remaining_size / full_size)
        # Plus 2 nights of remaining funding (day 10 after TP, day 11)
        # Trailing triggers on day 12 (index 11)
        funding_t2 = cum_at_tp * (remaining_size / full_size) + 2 * nr

        raw_pnl_t2 = (2080.0 - entry) * remaining_size  # 79 * 3.75 = 296.25
        assert raw_pnl_t2 == 296.25
        net_pnl_t2 = raw_pnl_t2 - funding_t2
        assert t2.pnl == pytest.approx(net_pnl_t2, rel=1e-6)
        assert t2.funding_cost == pytest.approx(funding_t2, rel=1e-6)

    def test_equity_consistency(self) -> None:
        """Final equity = starting_capital + sum(trade.pnl)."""
        result = self._run()
        _assert_equity_consistent(result, 100_000.0)

    def test_equity_curve_shape(self) -> None:
        """Equity curve has 25 rows with monotonic dates."""
        result = self._run()
        ec = result.equity_curve
        assert len(ec) == 25
        dates = list(ec.index)
        assert dates == sorted(dates)

    # -- helper --------------------------------------------------------

    @staticmethod
    def _run() -> BacktestResult:
        """Build and run Scenario A."""
        n = 25
        signals: list[float | str] = ["NEUTRAL"] * n
        signals[2] = "BUY"

        highs: list[float | str] = [2010.0] * n
        # Signal day (index 2): high=2000 for trap calc
        highs[2] = 2000.0
        # Fill day (index 3): high must >= buy_stop (2001)
        highs[3] = 2010.0
        # TP day (index 9): high >= 2151
        highs[9] = 2160.0
        # Day after TP (index 10): push highest_high to 2180
        highs[10] = 2180.0
        # Index 11: trailing triggers
        highs[11] = 2100.0

        lows: list[float | str] = [1990.0] * n
        lows[3] = 1990.0  # fill day
        lows[9] = 1990.0  # TP day, above SL
        lows[10] = 2100.0  # above trailing (2060 initially)
        lows[11] = 2075.0  # below trailing (2080 after HH update)

        closes: list[float | str] = [2000.0] * n

        return _build_scenario(
            n,
            overrides={
                "signal": signals,
                "high": highs,
                "low": lows,
                "close": closes,
            },
        )


# ------------------------------------------------------------------
# Scenario B: Stop loss exit
# ------------------------------------------------------------------


class TestScenarioB:
    """BUY fills, then SL triggers."""

    def test_single_sl_trade(self) -> None:
        """One trade closed at stop loss."""
        result = self._run()
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == ExitReason.STOP_LOSS
        assert t.entry_price == 2001.0
        assert t.exit_price == 1901.0
        assert t.size == 7.49

    def test_pnl_negative(self) -> None:
        """SL trade has negative raw P&L = -749.0 minus funding."""
        result = self._run()
        t = result.trades[0]

        # Fill at index 3, SL at index 5. Funding nights:
        # - Index 3 (fill day): Phase 2 runs, no exit -> 1 night
        # - Index 4: no exit -> 1 night
        # - Index 5: SL exit -> no funding
        # Total: 2 nights
        funding = 2 * _nightly_funding(2001.0, 7.49)
        raw = (1901.0 - 2001.0) * 7.49  # -749.0
        assert raw == -749.0
        expected_pnl = raw - funding
        assert t.pnl == pytest.approx(expected_pnl, rel=1e-6)

    def test_equity_consistency(self) -> None:
        """Final equity = starting_capital + trade.pnl."""
        result = self._run()
        _assert_equity_consistent(result, 100_000.0)

    @staticmethod
    def _run() -> BacktestResult:
        """Build and run Scenario B."""
        n = 10
        signals: list[float | str] = ["NEUTRAL"] * n
        signals[2] = "BUY"

        highs: list[float | str] = [2010.0] * n
        highs[2] = 2000.0  # signal day high for trap calc
        highs[3] = 2010.0  # fill day

        lows: list[float | str] = [1990.0] * n
        lows[3] = 1990.0  # fill day
        lows[5] = 1895.0  # SL hit (1895 <= 1901)

        return _build_scenario(
            n,
            overrides={"signal": signals, "high": highs, "low": lows},
        )


# ------------------------------------------------------------------
# Scenario C: No signals
# ------------------------------------------------------------------


class TestScenarioC:
    """All NEUTRAL signals produce zero trades."""

    def test_no_trades(self) -> None:
        """No signals means no trades."""
        result = _build_scenario(15)
        assert len(result.trades) == 0

    def test_flat_equity(self) -> None:
        """Equity stays at starting capital throughout."""
        result = _build_scenario(15)
        assert all(result.equity_curve["equity"] == 100_000.0)

    def test_equity_consistency(self) -> None:
        """Consistency check still holds with zero trades."""
        result = _build_scenario(15)
        _assert_equity_consistent(result, 100_000.0)


# ------------------------------------------------------------------
# Scenario D: Gap-through rejection
# ------------------------------------------------------------------


class TestScenarioD:
    """Gap-through: day_low > limit on fill day rejects fill."""

    def test_no_fill(self) -> None:
        """Gap-through means no fill, zero trades."""
        result = self._run()
        assert len(result.trades) == 0

    def test_equity_unchanged(self) -> None:
        """Equity remains flat at starting capital."""
        result = self._run()
        assert all(result.equity_curve["equity"] == 100_000.0)

    @staticmethod
    def _run() -> BacktestResult:
        """Build and run Scenario D.

        BUY signal on day 3, trap: buy_stop=2001, limit=2003.5
        Day 4: high=2010 (>= buy_stop), but low=2005 (> limit 2003.5) -> no fill
        """
        n = 10
        signals: list[float | str] = ["NEUTRAL"] * n
        signals[2] = "BUY"

        highs: list[float | str] = [2010.0] * n
        highs[2] = 2000.0  # signal day: buy_stop = 2000+0.02*50 = 2001

        lows: list[float | str] = [1990.0] * n
        lows[3] = 2005.0  # fill day: low=2005 > limit=2003.5 -> gap-through

        return _build_scenario(
            n,
            overrides={"signal": signals, "high": highs, "low": lows},
        )


# ------------------------------------------------------------------
# Scenario E: Time stop
# ------------------------------------------------------------------


class TestScenarioE:
    """Flat price for 10+ trading days triggers time stop at close."""

    def test_time_stop_exit(self) -> None:
        """Position exits on time stop after 10 days held."""
        result = self._run()
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == ExitReason.TIME_STOP
        assert t.days_held == 10
        assert t.entry_price == 2001.0
        assert t.exit_price == 2000.0  # closes at day close

    def test_pnl_with_funding(self) -> None:
        """P&L = raw loss from entry to close minus 9 nights of funding."""
        result = self._run()
        t = result.trades[0]

        # Position fills on day 2 (index 1). Phase 2 runs each day.
        # days_held 1..10. Exit on days_held=10.
        # Funding charged on days where no exit: days_held 1..9 => 9 nights.
        nf = _nightly_funding(2001.0, 7.49)
        total_funding = 9 * nf
        raw = (2000.0 - 2001.0) * 7.49  # -1 * 7.49 = -7.49
        expected = raw - total_funding
        assert t.pnl == pytest.approx(expected, rel=1e-6)
        assert t.funding_cost == pytest.approx(total_funding, rel=1e-6)

    def test_equity_consistency(self) -> None:
        """Final equity matches starting_capital + trade.pnl."""
        result = self._run()
        _assert_equity_consistent(result, 100_000.0)

    @staticmethod
    def _run() -> BacktestResult:
        """Build and run Scenario E.

        Signal on day 1 (index 0), fills day 2 (index 1).
        Flat price: no SL (low > 1901), no TP (high < 2151).
        Time stop fires on days_held=10 (day 11, index 10).
        """
        n = 15
        signals: list[float | str] = ["NEUTRAL"] * n
        signals[0] = "BUY"

        highs: list[float | str] = [2010.0] * n
        highs[0] = 2000.0  # signal day: buy_stop = 2001
        highs[1] = 2010.0  # fill day: high >= 2001

        lows: list[float | str] = [1990.0] * n
        lows[1] = 1990.0  # fill day: low <= 2003.5 (limit)

        closes: list[float | str] = [2000.0] * n

        return _build_scenario(
            n,
            overrides={
                "signal": signals,
                "high": highs,
                "low": lows,
                "close": closes,
            },
        )


# ------------------------------------------------------------------
# Scenario F: SL + TP same candle (SL wins)
# ------------------------------------------------------------------


class TestScenarioF:
    """When both SL and TP conditions are met on the same candle, SL wins."""

    def test_sl_wins_over_tp(self) -> None:
        """SL exit takes priority over TP on same candle."""
        result = self._run()
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == ExitReason.STOP_LOSS
        assert t.entry_price == 2001.0
        assert t.exit_price == 1901.0
        assert t.size == 7.49

    def test_equity_consistency(self) -> None:
        """Final equity = starting_capital + trade.pnl."""
        result = self._run()
        _assert_equity_consistent(result, 100_000.0)

    @staticmethod
    def _run() -> BacktestResult:
        """Build and run Scenario F.

        Signal day 1, fill day 2. On day 3 set a wide candle where:
          - low <= SL (1901) AND
          - high >= TP (2151)
        SL should win (conservative).
        """
        n = 10
        signals: list[float | str] = ["NEUTRAL"] * n
        signals[0] = "BUY"

        highs: list[float | str] = [2010.0] * n
        highs[0] = 2000.0  # signal day
        highs[1] = 2010.0  # fill day
        highs[2] = 2200.0  # wide candle: high >= TP (2151)

        lows: list[float | str] = [1990.0] * n
        lows[1] = 1990.0  # fill day
        lows[2] = 1850.0  # wide candle: low <= SL (1901)

        return _build_scenario(
            n,
            overrides={"signal": signals, "high": highs, "low": lows},
        )


# ------------------------------------------------------------------
# Scenario G: Equity consistency for all scenarios
# ------------------------------------------------------------------


class TestScenarioGEquityConsistency:
    """Equity consistency: starting + sum(pnl) = final equity for all scenarios."""

    def test_scenario_a(self) -> None:
        """Scenario A equity is consistent."""
        result = TestScenarioA._run()
        _assert_equity_consistent(result, 100_000.0)

    def test_scenario_b(self) -> None:
        """Scenario B equity is consistent."""
        result = TestScenarioB._run()
        _assert_equity_consistent(result, 100_000.0)

    def test_scenario_c(self) -> None:
        """Scenario C equity is consistent."""
        result = _build_scenario(15)
        _assert_equity_consistent(result, 100_000.0)

    def test_scenario_d(self) -> None:
        """Scenario D equity is consistent."""
        result = TestScenarioD._run()
        _assert_equity_consistent(result, 100_000.0)

    def test_scenario_e(self) -> None:
        """Scenario E equity is consistent."""
        result = TestScenarioE._run()
        _assert_equity_consistent(result, 100_000.0)

    def test_scenario_f(self) -> None:
        """Scenario F equity is consistent."""
        result = TestScenarioF._run()
        _assert_equity_consistent(result, 100_000.0)


# ------------------------------------------------------------------
# Scenario H: Metrics + Report integration
# ------------------------------------------------------------------


class TestScenarioHMetricsReport:
    """Run compute_metrics and generate_report on Scenario A output."""

    def test_metrics_keys(self) -> None:
        """Metrics dict contains all expected keys."""
        result = TestScenarioA._run()
        fedfunds = pd.Series([], dtype=float)
        metrics = compute_metrics(result, fedfunds)

        expected_keys = {
            "total_trades",
            "win_rate",
            "avg_win",
            "avg_loss",
            "avg_win_loss_ratio",
            "profit_factor",
            "max_drawdown_pct",
            "max_drawdown_duration",
            "avg_days_held",
            "total_costs",
            "total_return_pct",
            "annualized_return",
            "sharpe_ratio",
            "sortino_ratio",
        }
        assert set(metrics.keys()) == expected_keys

    def test_metrics_total_trades(self) -> None:
        """Scenario A produces 2 trades."""
        result = TestScenarioA._run()
        fedfunds = pd.Series([], dtype=float)
        metrics = compute_metrics(result, fedfunds)
        assert metrics["total_trades"] == 2.0

    def test_metrics_win_rate(self) -> None:
        """Both trades in Scenario A are winners."""
        result = TestScenarioA._run()
        fedfunds = pd.Series([], dtype=float)
        metrics = compute_metrics(result, fedfunds)
        assert metrics["win_rate"] == 1.0

    def test_metrics_total_return_positive(self) -> None:
        """Scenario A has positive total return."""
        result = TestScenarioA._run()
        fedfunds = pd.Series([], dtype=float)
        metrics = compute_metrics(result, fedfunds)
        assert metrics["total_return_pct"] > 0.0

    def test_generate_report_html(self) -> None:
        """generate_report returns valid HTML with expected sections."""
        result = TestScenarioA._run()
        fedfunds = pd.Series([], dtype=float)
        metrics = compute_metrics(result, fedfunds)
        html = generate_report(result, metrics)

        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")
        assert "Backtest Report" in html
        assert "Metrics Summary" in html
        assert "Equity Curve" in html
        assert "Drawdown" in html
        assert "Monthly Returns" in html
        assert "Trade Log" in html
        assert "TAKE_PROFIT" in html
        assert "TRAILING_STOP" in html
