"""Tests for generate_report: Plotly HTML report generation."""

import datetime

import numpy as np
import pandas as pd

from trading_advisor.backtest.engine import BacktestResult, ExitReason, Trade
from trading_advisor.backtest.report import generate_report

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_trade(
    entry_date: datetime.date,
    exit_date: datetime.date,
    pnl: float,
    entry_price: float = 100.0,
    exit_price: float | None = None,
    size: float = 1.0,
    days_held: int = 3,
    spread_cost: float = 0.5,
    slippage_cost: float = 0.2,
    funding_cost: float = 0.1,
    exit_reason: ExitReason = ExitReason.TAKE_PROFIT,
) -> Trade:
    """Build a Trade with given dates and pnl."""
    if exit_price is None:
        exit_price = entry_price + pnl
    return Trade(
        entry_date=entry_date,
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        size=size,
        direction="LONG",
        pnl=pnl,
        exit_reason=exit_reason,
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
    """Build a BacktestResult with the given trades and equity curve."""
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


def _make_result_empty_equity() -> BacktestResult:
    """Build a BacktestResult with an empty equity curve."""
    dates: pd.DatetimeIndex = pd.DatetimeIndex([])
    equity_curve = pd.DataFrame(
        {"equity": [], "drawdown_pct": [], "throttle_state": []},
        index=dates,
    )
    return BacktestResult(
        equity_curve=equity_curve,
        trades=(),
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 1, 1),
        starting_capital=15000.0,
    )


def _typical_result() -> BacktestResult:
    """Build a representative BacktestResult spanning a few months."""
    # Use ~90 business days so monthly returns heatmap has multiple months
    n = 90
    dates = pd.bdate_range("2024-01-01", periods=n, freq="B")
    # Gently rising equity with one dip
    equity_values = [15000.0 + i * 10 + (50.0 if i < 45 else -50.0) for i in range(n)]
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
    t1 = _make_trade(
        datetime.date(2024, 1, 5),
        datetime.date(2024, 1, 12),
        pnl=200.0,
    )
    t2 = _make_trade(
        datetime.date(2024, 2, 1),
        datetime.date(2024, 2, 8),
        pnl=-80.0,
        exit_reason=ExitReason.STOP_LOSS,
    )
    return BacktestResult(
        equity_curve=equity_curve,
        trades=(t1, t2),
        start_date=dates[0].date(),
        end_date=dates[-1].date(),
        starting_capital=15000.0,
    )


def _typical_metrics() -> dict[str, float]:
    """Return a representative metrics dict."""
    return {
        "total_trades": 2.0,
        "win_rate": 0.5,
        "avg_win": 200.0,
        "avg_loss": 80.0,
        "avg_win_loss_ratio": 2.5,
        "profit_factor": 2.5,
        "max_drawdown_pct": 0.03,
        "max_drawdown_duration": 5.0,
        "avg_days_held": 7.0,
        "total_costs": 3.2,
        "total_return_pct": 6.0,
        "annualized_return": 0.12,
        "sharpe_ratio": 1.1,
        "sortino_ratio": 1.5,
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestGenerateReportHtml:
    """Tests that verify the HTML output structure of generate_report."""

    def test_returns_non_empty_string(self) -> None:
        """generate_report returns a non-empty string."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert isinstance(html, str)
        assert len(html) > 0

    def test_starts_with_doctype(self) -> None:
        """Output starts with <!DOCTYPE html>."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_contains_closing_html_tag(self) -> None:
        """Output contains </html>."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert "</html>" in html

    def test_contains_equity_curve_title(self) -> None:
        """Output contains 'Equity Curve' as a chart title."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert "Equity Curve" in html

    def test_contains_plotly_cdn_reference(self) -> None:
        """Output contains 'plotly' (CDN script reference)."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert "plotly" in html.lower()

    def test_contains_drawdown_section(self) -> None:
        """Output contains 'Drawdown' as a section/chart title."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert "Drawdown" in html

    def test_contains_monthly_returns_section(self) -> None:
        """Output contains 'Monthly Returns' as a section title."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert "Monthly Returns" in html


class TestGenerateReportMetrics:
    """Tests that verify metrics values appear in the HTML output."""

    def test_contains_total_trades_value(self) -> None:
        """Output contains the total_trades value as a string."""
        result = _typical_result()
        metrics = _typical_metrics()
        html = generate_report(result, metrics)
        # total_trades = 2.0 -> should appear as "2" in the table
        assert "2" in html

    def test_contains_sharpe_ratio_value(self) -> None:
        """Output contains sharpe_ratio formatted to 2 decimal places."""
        result = _typical_result()
        metrics = _typical_metrics()
        html = generate_report(result, metrics)
        # sharpe_ratio = 1.1 -> should appear as "1.10" in the table
        assert "1.10" in html

    def test_contains_win_rate_value(self) -> None:
        """Output contains win_rate formatted to 2 decimal places."""
        result = _typical_result()
        metrics = _typical_metrics()
        html = generate_report(result, metrics)
        # win_rate = 0.5 -> should appear as "0.50" in the table
        assert "0.50" in html

    def test_metrics_keys_appear_in_table(self) -> None:
        """Each metric key appears in the HTML output (as a table header/cell)."""
        result = _typical_result()
        metrics = _typical_metrics()
        html = generate_report(result, metrics)
        for key in metrics:
            assert key in html, f"Metric key '{key}' not found in HTML output"


class TestGenerateReportTradeLog:
    """Tests that verify trade log content in the HTML output."""

    def test_contains_entry_date(self) -> None:
        """Output contains the entry date of the first trade."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        # First trade entry_date = 2024-01-05
        assert "2024-01-05" in html

    def test_contains_exit_date(self) -> None:
        """Output contains the exit date of the first trade."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        # First trade exit_date = 2024-01-12
        assert "2024-01-12" in html

    def test_contains_exit_reason(self) -> None:
        """Output contains the exit reason of a trade."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert "TAKE_PROFIT" in html or "STOP_LOSS" in html

    def test_trade_log_has_headers(self) -> None:
        """Trade log table contains expected column headers."""
        result = _typical_result()
        html = generate_report(result, _typical_metrics())
        assert "Entry Date" in html
        assert "Exit Date" in html
        assert "P&amp;L" in html or "P&L" in html


class TestGenerateReportEmptyTrades:
    """Tests for generate_report when there are no trades."""

    def test_empty_trades_report_generates(self) -> None:
        """Report still generates when there are no trades."""
        result = _make_result([], [15000.0, 15100.0, 15050.0, 15125.0])
        metrics: dict[str, float] = {
            "total_trades": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "avg_win_loss_ratio": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_duration": 0.0,
            "avg_days_held": 0.0,
            "total_costs": 0.0,
            "total_return_pct": 0.83,
            "annualized_return": 0.02,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
        }
        html = generate_report(result, metrics)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_empty_trades_contains_no_trades_message(self) -> None:
        """Report for empty trade list contains 'No trades' message."""
        result = _make_result([], [15000.0, 15100.0, 15050.0, 15125.0])
        metrics: dict[str, float] = {
            "total_trades": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "avg_win_loss_ratio": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_duration": 0.0,
            "avg_days_held": 0.0,
            "total_costs": 0.0,
            "total_return_pct": 0.83,
            "annualized_return": 0.02,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
        }
        html = generate_report(result, metrics)
        assert "No trades" in html

    def test_empty_trades_html_structure_intact(self) -> None:
        """HTML structure is valid even with empty trades."""
        result = _make_result([], [15000.0, 15100.0, 15050.0])
        metrics: dict[str, float] = {"total_trades": 0.0}
        html = generate_report(result, metrics)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html


class TestGenerateReportEmptyEquityCurve:
    """Tests for generate_report when equity curve is empty."""

    def test_empty_equity_curve_report_generates(self) -> None:
        """Report generates even with an empty equity curve."""
        result = _make_result_empty_equity()
        metrics: dict[str, float] = {
            "total_trades": 0.0,
            "win_rate": 0.0,
        }
        html = generate_report(result, metrics)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_empty_equity_curve_html_structure_intact(self) -> None:
        """HTML structure is valid even with empty equity curve."""
        result = _make_result_empty_equity()
        metrics: dict[str, float] = {"total_trades": 0.0}
        html = generate_report(result, metrics)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html
        assert "Equity Curve" in html
        assert "Drawdown" in html
