"""Tests for backtest report metrics computation."""

import datetime

import numpy as np
import pandas as pd
import pytest

from trading_advisor.backtest.engine import BacktestResult, ExitReason, Trade
from trading_advisor.backtest.report import compute_metrics

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_trade(
    pnl: float,
    days_held: int = 1,
    spread_cost: float = 0.0,
    slippage_cost: float = 0.0,
    funding_cost: float = 0.0,
) -> Trade:
    """Build a minimal Trade with the given pnl and cost fields."""
    return Trade(
        entry_date=datetime.date(2024, 1, 1),
        exit_date=datetime.date(2024, 1, 2),
        entry_price=100.0,
        exit_price=100.0 + pnl,
        size=1.0,
        direction="LONG",
        pnl=pnl,
        exit_reason=ExitReason.STOP_LOSS,
        days_held=days_held,
        spread_cost=spread_cost,
        slippage_cost=slippage_cost,
        funding_cost=funding_cost,
    )


def _make_result(
    trades: list[Trade],
    equity_values: list[float],
    starting_capital: float = 15000.0,
) -> BacktestResult:
    """Build a BacktestResult with given trades and equity curve."""
    n = len(equity_values)
    dates = pd.bdate_range("2024-01-01", periods=n, freq="B")
    equities = np.array(equity_values, dtype=float)
    hwm = np.maximum.accumulate(equities)
    drawdown_pct = np.where(hwm > 0, (hwm - equities) / hwm, 0.0)
    equity_curve = pd.DataFrame(
        {
            "equity": equity_values,
            "drawdown_pct": drawdown_pct.tolist(),
            "throttle_state": ["NORMAL"] * n,
        },
        index=dates,
    )
    return BacktestResult(
        equity_curve=equity_curve,
        trades=tuple(trades),
        start_date=dates[0].date(),
        end_date=dates[-1].date(),
        starting_capital=starting_capital,
    )


def _empty_fedfunds() -> "pd.Series[float]":
    """Return an empty fedfunds Series."""
    return pd.Series([], dtype=float)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestThreeTrades:
    """Three trades: pnl=[+100, -50, +75]."""

    @pytest.fixture()
    def metrics(self) -> dict[str, float]:
        """Compute metrics for 3 trades."""
        trades = [
            _make_trade(100.0, days_held=3),
            _make_trade(-50.0, days_held=2),
            _make_trade(75.0, days_held=5),
        ]
        result = _make_result(
            trades,
            [15000.0, 15100.0, 15050.0, 15125.0],
        )
        return compute_metrics(result, _empty_fedfunds())

    def test_total_trades(self, metrics: dict[str, float]) -> None:
        assert metrics["total_trades"] == 3

    def test_win_rate(self, metrics: dict[str, float]) -> None:
        assert metrics["win_rate"] == pytest.approx(2 / 3)

    def test_avg_win(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_win"] == pytest.approx(87.5)

    def test_avg_loss(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_loss"] == pytest.approx(50.0)

    def test_avg_win_loss_ratio(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_win_loss_ratio"] == pytest.approx(1.75)

    def test_profit_factor(self, metrics: dict[str, float]) -> None:
        assert metrics["profit_factor"] == pytest.approx(3.5)

    def test_total_return_pct(self, metrics: dict[str, float]) -> None:
        expected = (15125.0 - 15000.0) / 15000.0 * 100
        assert metrics["total_return_pct"] == pytest.approx(expected)

    def test_avg_days_held(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_days_held"] == pytest.approx(10 / 3)


class TestNoTrades:
    """Empty trade list with flat equity."""

    @pytest.fixture()
    def metrics(self) -> dict[str, float]:
        """Compute metrics with no trades."""
        result = _make_result([], [15000.0, 15000.0, 15000.0])
        return compute_metrics(result, _empty_fedfunds())

    def test_total_trades(self, metrics: dict[str, float]) -> None:
        assert metrics["total_trades"] == 0

    def test_win_rate(self, metrics: dict[str, float]) -> None:
        assert metrics["win_rate"] == 0.0

    def test_avg_win(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_win"] == 0.0

    def test_avg_loss(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_loss"] == 0.0

    def test_avg_win_loss_ratio(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_win_loss_ratio"] == 0.0

    def test_profit_factor(self, metrics: dict[str, float]) -> None:
        assert metrics["profit_factor"] == 0.0

    def test_total_return_pct(self, metrics: dict[str, float]) -> None:
        assert metrics["total_return_pct"] == 0.0

    def test_sharpe(self, metrics: dict[str, float]) -> None:
        assert metrics["sharpe_ratio"] == 0.0

    def test_sortino(self, metrics: dict[str, float]) -> None:
        assert metrics["sortino_ratio"] == 0.0

    def test_max_drawdown_pct(self, metrics: dict[str, float]) -> None:
        assert metrics["max_drawdown_pct"] == 0.0

    def test_max_drawdown_duration(self, metrics: dict[str, float]) -> None:
        assert metrics["max_drawdown_duration"] == 0

    def test_avg_days_held(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_days_held"] == 0.0

    def test_total_costs(self, metrics: dict[str, float]) -> None:
        assert metrics["total_costs"] == 0.0


class TestAllWins:
    """Three trades all positive."""

    @pytest.fixture()
    def metrics(self) -> dict[str, float]:
        """Compute metrics for all-winning trades."""
        trades = [_make_trade(100.0), _make_trade(50.0), _make_trade(75.0)]
        result = _make_result(
            trades,
            [10000.0, 10100.0, 10150.0, 10225.0],
            starting_capital=10000.0,
        )
        return compute_metrics(result, _empty_fedfunds())

    def test_profit_factor(self, metrics: dict[str, float]) -> None:
        assert metrics["profit_factor"] == float("inf")

    def test_avg_loss(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_loss"] == 0.0

    def test_avg_win_loss_ratio(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_win_loss_ratio"] == float("inf")

    def test_win_rate(self, metrics: dict[str, float]) -> None:
        assert metrics["win_rate"] == 1.0


class TestAllLosses:
    """Three trades all negative."""

    @pytest.fixture()
    def metrics(self) -> dict[str, float]:
        """Compute metrics for all-losing trades."""
        trades = [_make_trade(-100.0), _make_trade(-50.0), _make_trade(-75.0)]
        result = _make_result(
            trades,
            [10000.0, 9900.0, 9850.0, 9775.0],
            starting_capital=10000.0,
        )
        return compute_metrics(result, _empty_fedfunds())

    def test_profit_factor(self, metrics: dict[str, float]) -> None:
        assert metrics["profit_factor"] == 0.0

    def test_win_rate(self, metrics: dict[str, float]) -> None:
        assert metrics["win_rate"] == 0.0

    def test_avg_win(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_win"] == 0.0

    def test_avg_win_loss_ratio(self, metrics: dict[str, float]) -> None:
        assert metrics["avg_win_loss_ratio"] == 0.0


class TestBreakevenTrade:
    """Trades including a zero-PnL (breakeven) trade."""

    @pytest.fixture()
    def metrics(self) -> dict[str, float]:
        """Compute metrics with one win, one breakeven, one loss."""
        trades = [_make_trade(100.0), _make_trade(0.0), _make_trade(-50.0)]
        result = _make_result(
            trades,
            [10000.0, 10100.0, 10100.0, 10050.0],
            starting_capital=10000.0,
        )
        return compute_metrics(result, _empty_fedfunds())

    def test_win_rate(self, metrics: dict[str, float]) -> None:
        """Breakeven trade is neither win nor loss; win_rate = 1/3."""
        assert metrics["win_rate"] == pytest.approx(1.0 / 3.0)

    def test_profit_factor(self, metrics: dict[str, float]) -> None:
        """Breakeven trade excluded from both sides: 100/50 = 2.0."""
        assert metrics["profit_factor"] == pytest.approx(2.0)

    def test_avg_win(self, metrics: dict[str, float]) -> None:
        """Only the +100 trade is a win."""
        assert metrics["avg_win"] == pytest.approx(100.0)

    def test_avg_loss(self, metrics: dict[str, float]) -> None:
        """Only the -50 trade is a loss."""
        assert metrics["avg_loss"] == pytest.approx(50.0)


class TestSharpeRatio:
    """Sharpe ratio with a known equity curve and empty fedfunds."""

    def test_sharpe_computation(self) -> None:
        equity_values = [10000.0, 10200.0, 9800.0, 10100.0, 9900.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())

        # Hand-compute expected Sharpe
        equity = pd.Series(equity_values)
        daily_returns = equity.pct_change().dropna()
        daily_rf = 0.0
        excess = daily_returns - daily_rf
        mean_excess = float(excess.mean())
        std_excess = float(excess.std(ddof=1))
        expected_sharpe = (mean_excess / std_excess) * np.sqrt(252)

        assert metrics["sharpe_ratio"] == pytest.approx(expected_sharpe)

    def test_sharpe_with_fedfunds(self) -> None:
        equity_values = [10000.0, 10200.0, 9800.0, 10100.0, 9900.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        # Fedfunds of 5% over the period (FRED stores as percentage)
        dates = pd.bdate_range("2024-01-01", periods=5, freq="B")
        fedfunds = pd.Series([5.0, 5.0, 5.0, 5.0, 5.0], index=dates)
        metrics = compute_metrics(result, fedfunds)

        equity = pd.Series(equity_values)
        daily_returns = equity.pct_change().dropna()
        daily_rf = 0.05 / 252
        excess = daily_returns - daily_rf
        mean_excess = float(excess.mean())
        std_excess = float(excess.std(ddof=1))
        expected_sharpe = (mean_excess / std_excess) * np.sqrt(252)

        assert metrics["sharpe_ratio"] == pytest.approx(expected_sharpe)

    def test_sharpe_zero_std(self) -> None:
        """Constant equity -> std=0 -> sharpe=0."""
        equity_values = [10000.0, 10000.0, 10000.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["sharpe_ratio"] == 0.0


class TestSortinoRatio:
    """Sortino ratio with a known equity curve."""

    def test_sortino_computation(self) -> None:
        equity_values = [10000.0, 10200.0, 9800.0, 10100.0, 9900.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())

        equity = pd.Series(equity_values)
        daily_returns = equity.pct_change().dropna()
        daily_rf = 0.0
        excess = daily_returns - daily_rf
        mean_excess = float(excess.mean())
        downside = excess[excess < 0]
        downside_std = float(np.sqrt((downside**2).mean()))
        expected_sortino = (mean_excess / downside_std) * np.sqrt(252)

        assert metrics["sortino_ratio"] == pytest.approx(expected_sortino)

    def test_sortino_all_positive_excess(self) -> None:
        """All positive daily returns -> no downside -> sortino=inf."""
        equity_values = [10000.0, 10100.0, 10200.0, 10300.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["sortino_ratio"] == float("inf")


class TestMaxDrawdownDuration:
    """Max drawdown duration from equity dips and recoveries."""

    def test_two_equal_streaks(self) -> None:
        # equity = [10000, 10000, 9500, 9800, 9900, 10000, 9600, 9700, 9800, 10100]
        # HWM:     [10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10100]
        # DD>0:    [  F,     F,     T,     T,     T,     F,     T,     T,     T,     F   ]
        # Streaks: 3, 3 -> max = 3
        equity_values = [
            10000.0,
            10000.0,
            9500.0,
            9800.0,
            9900.0,
            10000.0,
            9600.0,
            9700.0,
            9800.0,
            10100.0,
        ]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["max_drawdown_duration"] == 3

    def test_no_drawdown(self) -> None:
        equity_values = [10000.0, 10100.0, 10200.0, 10300.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["max_drawdown_duration"] == 0

    def test_max_drawdown_pct(self) -> None:
        # DD_pct: max is at 9500 -> (10000-9500)/10000 = 0.05
        equity_values = [10000.0, 10000.0, 9500.0, 9800.0, 10100.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["max_drawdown_pct"] == pytest.approx(0.05)


class TestAnnualizedReturn:
    """Annualized return formula verification."""

    def test_one_year(self) -> None:
        """252 trading days, 10% total return -> annualized = 10%."""
        equity_values = list(np.linspace(10000.0, 11000.0, 252))
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["annualized_return"] == pytest.approx(0.1)

    def test_zero_trading_days(self) -> None:
        """Edge case: single-day equity curve -> trading_days=1."""
        # With 1 day, formula is: (equity/capital)^(252/1) - 1
        result = _make_result([], [10000.0], starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        # (10000/10000)^252 - 1 = 0.0
        assert metrics["annualized_return"] == pytest.approx(0.0)


class TestTotalCosts:
    """Verify costs are summed correctly from trades."""

    def test_costs_summed(self) -> None:
        trades = [
            _make_trade(100.0, spread_cost=5.0, slippage_cost=2.0, funding_cost=1.5),
            _make_trade(-50.0, spread_cost=3.0, slippage_cost=1.0, funding_cost=0.5),
        ]
        result = _make_result(trades, [10000.0, 10050.0], starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        # total = (5+2+1.5) + (3+1+0.5) = 8.5 + 4.5 = 13.0
        assert metrics["total_costs"] == pytest.approx(13.0)

    def test_no_trades_zero_costs(self) -> None:
        result = _make_result([], [10000.0, 10000.0], starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["total_costs"] == 0.0


class TestEdgeCases:
    """Edge cases for complete branch coverage."""

    def test_empty_equity_curve(self) -> None:
        """Empty equity curve returns all-zero metrics."""
        dates: pd.DatetimeIndex = pd.DatetimeIndex([])
        equity_curve = pd.DataFrame(
            {"equity": [], "drawdown_pct": [], "throttle_state": []},
            index=dates,
        )
        result = BacktestResult(
            equity_curve=equity_curve,
            trades=(),
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 1, 1),
            starting_capital=10000.0,
        )
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["total_trades"] == 0
        assert metrics["sharpe_ratio"] == 0.0
        assert metrics["sortino_ratio"] == 0.0
        assert metrics["annualized_return"] == 0.0

    def test_complete_loss(self) -> None:
        """Equity goes to zero -> annualized_return = -1.0."""
        result = _make_result(
            [_make_trade(-10000.0)],
            [10000.0, 0.0],
            starting_capital=10000.0,
        )
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["annualized_return"] == -1.0

    def test_fedfunds_out_of_range(self) -> None:
        """Non-empty fedfunds but dates don't overlap -> daily_rf=0."""
        equity_values = [10000.0, 10200.0, 9800.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        # Fedfunds in 2023, but equity curve starts 2024
        ff_dates = pd.bdate_range("2023-01-01", periods=3, freq="B")
        fedfunds = pd.Series([5.0, 5.0, 5.0], index=ff_dates)
        metrics = compute_metrics(result, fedfunds)

        # With daily_rf=0, same as empty fedfunds
        equity = pd.Series(equity_values)
        daily_returns = equity.pct_change().dropna()
        mean_excess = float(daily_returns.mean())
        std_excess = float(daily_returns.std(ddof=1))
        expected_sharpe = (mean_excess / std_excess) * np.sqrt(252)
        assert metrics["sharpe_ratio"] == pytest.approx(expected_sharpe)

    def test_sortino_negative_mean_with_no_downside(self) -> None:
        """Sortino with mean_excess == 0 and no downside returns 0."""
        # Flat equity: all returns are 0, no downside
        equity_values = [10000.0, 10000.0, 10000.0, 10000.0]
        result = _make_result([], equity_values, starting_capital=10000.0)
        metrics = compute_metrics(result, _empty_fedfunds())
        assert metrics["sortino_ratio"] == 0.0
