"""Backtest report: performance metrics, equity curve charts, monthly heatmap.

compute_metrics: Sharpe, Sortino, Profit Factor, Max Drawdown, Win Rate, etc.
generate_report: Plotly HTML with equity curve, drawdown, monthly returns heatmap,
    metrics summary table, and trade log.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from trading_advisor.backtest.engine import BacktestResult


def compute_metrics(
    result: BacktestResult,
    fedfunds: "pd.Series[float]",
) -> dict[str, float]:
    """Compute performance metrics from a completed backtest.

    Args:
        result: The BacktestResult from run_backtest.
        fedfunds: Series indexed by DatetimeIndex with FEDFUNDS rates.
            Used for risk-free rate in Sharpe/Sortino calculations.

    Returns:
        Dictionary of metric name to value.
    """
    trades = result.trades
    equity_curve = result.equity_curve
    starting_capital = result.starting_capital
    total_trades = len(trades)
    trading_days = len(equity_curve)

    # -- Trade-based metrics -------------------------------------------
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean([abs(p) for p in losses])) if losses else 0.0

    if avg_win == 0.0:
        avg_win_loss_ratio = 0.0
    elif avg_loss == 0.0:
        avg_win_loss_ratio = float("inf")
    else:
        avg_win_loss_ratio = avg_win / avg_loss

    sum_wins = sum(wins)
    sum_losses = abs(sum(losses))
    if not wins:
        profit_factor = 0.0
    elif sum_losses == 0.0:
        profit_factor = float("inf")
    else:
        profit_factor = sum_wins / sum_losses

    avg_days_held = float(np.mean([t.days_held for t in trades])) if total_trades > 0 else 0.0

    total_costs = (
        sum(t.spread_cost + t.slippage_cost + t.funding_cost for t in trades)
        if total_trades > 0
        else 0.0
    )

    # -- Equity-based metrics ------------------------------------------
    if trading_days == 0:
        return {
            "total_trades": float(total_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_win_loss_ratio": avg_win_loss_ratio,
            "profit_factor": profit_factor,
            "max_drawdown_pct": 0.0,
            "max_drawdown_duration": 0.0,
            "avg_days_held": avg_days_held,
            "total_costs": total_costs,
            "total_return_pct": 0.0,
            "annualized_return": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
        }

    final_equity = float(equity_curve["equity"].iloc[-1])
    total_return_pct = (final_equity - starting_capital) / starting_capital * 100

    # Annualized return
    ratio = final_equity / starting_capital
    annualized_return = -1.0 if ratio <= 0 else ratio ** (252 / trading_days) - 1

    # Max drawdown pct
    dd_col = equity_curve["drawdown_pct"]
    max_drawdown_pct = float(dd_col.max()) if len(dd_col) > 0 else 0.0

    # Max drawdown duration: longest streak of consecutive rows where dd > 0
    max_dd_duration = 0
    current_streak = 0
    for dd_val in dd_col:
        if float(dd_val) > 0:
            current_streak += 1
            max_dd_duration = max(max_dd_duration, current_streak)
        else:
            current_streak = 0

    # -- Risk-adjusted metrics -----------------------------------------
    equity_series: pd.Series[float] = equity_curve["equity"]
    daily_returns: pd.Series[float] = equity_series.pct_change().dropna()

    # Daily risk-free rate from fedfunds
    if fedfunds.empty:
        daily_rf = 0.0
    else:
        # Filter fedfunds to the backtest date range
        start_date = equity_curve.index[0]
        end_date = equity_curve.index[-1]
        mask = (fedfunds.index >= start_date) & (fedfunds.index <= end_date)
        in_range = fedfunds.loc[mask]
        daily_rf = 0.0 if len(in_range) == 0 else float(in_range.mean()) / 252

    excess = daily_returns - daily_rf

    if len(daily_returns) == 0:
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
    else:
        mean_excess = float(excess.mean())
        std_daily = float(excess.std(ddof=1))

        # Sharpe
        sharpe_ratio = 0.0 if std_daily == 0.0 else (mean_excess / std_daily) * float(np.sqrt(252))

        # Sortino
        downside = excess[excess < 0]
        if len(downside) == 0:
            sortino_ratio = float("inf") if mean_excess > 0 else 0.0
        else:
            downside_std = float(np.sqrt(float((downside**2).mean())))
            if downside_std == 0.0:  # pragma: no cover — downside is < 0 so std > 0
                sortino_ratio = 0.0
            else:
                sortino_ratio = (mean_excess / downside_std) * float(np.sqrt(252))

    return {
        "total_trades": float(total_trades),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_win_loss_ratio": avg_win_loss_ratio,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown_pct,
        "max_drawdown_duration": float(max_dd_duration),
        "avg_days_held": avg_days_held,
        "total_costs": total_costs,
        "total_return_pct": total_return_pct,
        "annualized_return": annualized_return,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
    }


# ------------------------------------------------------------------
# HTML report
# ------------------------------------------------------------------


def _build_metrics_table(metrics: dict[str, float]) -> str:
    """Build an HTML table of metric name/value pairs.

    Args:
        metrics: Mapping of metric name to float value.

    Returns:
        HTML string for a two-column table.
    """
    rows: list[str] = []
    for name, value in metrics.items():
        formatted = f"{value:.2f}"
        rows.append(f"<tr><td>{name}</td><td>{formatted}</td></tr>")
    body = "\n".join(rows)
    return (
        "<table>\n"
        "<thead><tr><th>Metric</th><th>Value</th></tr></thead>\n"
        f"<tbody>{body}</tbody>\n"
        "</table>"
    )


def _build_trade_log_table(result: BacktestResult) -> str:
    """Build an HTML table listing all completed trades.

    Args:
        result: The BacktestResult containing the trade list.

    Returns:
        HTML string for the trade log table, or a "No trades" message when empty.
    """
    if not result.trades:
        return "<p>No trades</p>"

    headers = [
        "Entry Date",
        "Exit Date",
        "Entry Price",
        "Exit Price",
        "Size",
        "Direction",
        "P&amp;L",
        "Exit Reason",
        "Days Held",
        "Costs",
    ]
    header_row = "".join(f"<th>{h}</th>" for h in headers)
    rows: list[str] = []
    for t in result.trades:
        total_costs = t.spread_cost + t.slippage_cost + t.funding_cost
        pnl_class = "positive" if t.pnl >= 0 else "negative"
        cells = [
            f"<td>{t.entry_date}</td>",
            f"<td>{t.exit_date}</td>",
            f"<td>{t.entry_price:.2f}</td>",
            f"<td>{t.exit_price:.2f}</td>",
            f"<td>{t.size:.2f}</td>",
            f"<td>{t.direction}</td>",
            f'<td class="{pnl_class}">{t.pnl:.2f}</td>',
            f"<td>{t.exit_reason.value}</td>",
            f"<td>{t.days_held}</td>",
            f"<td>{total_costs:.2f}</td>",
        ]
        rows.append(f"<tr>{''.join(cells)}</tr>")

    body = "\n".join(rows)
    return (
        "<table>\n" f"<thead><tr>{header_row}</tr></thead>\n" f"<tbody>{body}</tbody>\n" "</table>"
    )


def _build_equity_chart(result: BacktestResult) -> str:
    """Build a Plotly equity curve chart as an HTML div string.

    Args:
        result: The BacktestResult containing the equity curve.

    Returns:
        HTML div string for the equity curve chart.
    """
    equity_curve = result.equity_curve
    if equity_curve.empty:
        dates: list[object] = []
        equity_vals: list[float] = []
    else:
        dates = list(equity_curve.index)
        equity_vals = list(equity_curve["equity"].astype(float))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=equity_vals,
            mode="lines",
            line={"color": "#00ff88"},
            name="Equity",
        )
    )
    fig.update_layout(
        title="Equity Curve",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font={"color": "#e0e0e0"},
        xaxis={"gridcolor": "#333"},
        yaxis={"gridcolor": "#333"},
    )
    return str(fig.to_html(include_plotlyjs="cdn", full_html=False))


def _build_drawdown_chart(result: BacktestResult) -> str:
    """Build a Plotly drawdown chart as an HTML div string.

    The drawdown is displayed inverted (negative values below zero) with a
    red fill to emphasise underwater periods.

    Args:
        result: The BacktestResult containing the equity curve.

    Returns:
        HTML div string for the drawdown chart.
    """
    equity_curve = result.equity_curve
    if equity_curve.empty:
        dates: list[object] = []
        dd_vals: list[float] = []
    else:
        dates = list(equity_curve.index)
        dd_vals = [-float(v) for v in equity_curve["drawdown_pct"]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=dd_vals,
            mode="lines",
            fill="tozeroy",
            line={"color": "#ff4444"},
            fillcolor="rgba(255,68,68,0.3)",
            name="Drawdown",
        )
    )
    fig.update_layout(
        title="Drawdown",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font={"color": "#e0e0e0"},
        xaxis={"gridcolor": "#333"},
        yaxis={"gridcolor": "#333"},
    )
    return str(fig.to_html(include_plotlyjs=False, full_html=False))


def _build_monthly_heatmap(result: BacktestResult) -> str:
    """Build a Plotly monthly returns heatmap as an HTML div string.

    Rows are years, columns are months (Jan–Dec). Each cell shows the
    monthly return as a percentage. Green = positive, red = negative.

    Args:
        result: The BacktestResult containing the equity curve.

    Returns:
        HTML div string for the monthly returns heatmap.
    """
    equity_curve = result.equity_curve
    if equity_curve.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Monthly Returns",
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#16213e",
            font={"color": "#e0e0e0"},
        )
        return str(fig.to_html(include_plotlyjs=False, full_html=False))

    equity_series: pd.Series[float] = equity_curve["equity"].astype(float)
    # Resample to last value per calendar month
    monthly: pd.Series[float] = equity_series.resample("ME").last()
    monthly_returns: pd.Series[float] = monthly.pct_change() * 100.0

    # Build a pivot: rows = years, cols = month numbers 1..12
    monthly_dt_index = pd.DatetimeIndex(monthly_returns.index)
    df = pd.DataFrame(
        {
            "year": monthly_dt_index.year,
            "month": monthly_dt_index.month,
            "return": monthly_returns.values,
        }
    )
    pivot = df.pivot(index="year", columns="month", values="return")
    # Ensure all 12 months are present as columns
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = float("nan")
    pivot = pivot[[m for m in range(1, 13)]]

    month_labels = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    year_labels = [str(y) for y in pivot.index]
    z_values = pivot.values.tolist()

    # Build text annotations showing percentage values
    text_values = [[f"{v:.1f}%" if not np.isnan(v) else "" for v in row] for row in z_values]

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=month_labels,
            y=year_labels,
            text=text_values,
            texttemplate="%{text}",
            colorscale=[
                [0.0, "#ff4444"],
                [0.5, "#333333"],
                [1.0, "#00ff88"],
            ],
            zmid=0.0,
            showscale=True,
        )
    )
    fig.update_layout(
        title="Monthly Returns",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font={"color": "#e0e0e0"},
    )
    return str(fig.to_html(include_plotlyjs=False, full_html=False))


def generate_report(
    result: BacktestResult,
    metrics: dict[str, float],
) -> str:
    """Generate a self-contained HTML report with charts and tables.

    Sections:
      1. Metrics summary table
      2. Equity curve line chart
      3. Drawdown area chart (inverted, red fill)
      4. Monthly returns heatmap (years x months, green/red)
      5. Trade log table

    Args:
        result: The BacktestResult from run_backtest.
        metrics: Metrics dictionary from compute_metrics.

    Returns:
        Self-contained HTML string.
    """
    metrics_table = _build_metrics_table(metrics)
    equity_chart = _build_equity_chart(result)
    drawdown_chart = _build_drawdown_chart(result)
    monthly_heatmap = _build_monthly_heatmap(result)
    trade_log = _build_trade_log_table(result)

    html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "    <title>Backtest Report</title>\n"
        "    <style>\n"
        "        body { font-family: Arial, sans-serif; margin: 20px;"
        " background: #1a1a2e; color: #e0e0e0; }\n"
        "        table { border-collapse: collapse; width: 100%; margin: 20px 0; }\n"
        "        th, td { border: 1px solid #333; padding: 8px; text-align: right; }\n"
        "        th { background: #16213e; }\n"
        "        h1, h2 { color: #e0e0e0; }\n"
        "        .positive { color: #00ff88; }\n"
        "        .negative { color: #ff4444; }\n"
        "    </style>\n"
        "</head>\n"
        "<body>\n"
        "    <h1>Backtest Report</h1>\n"
        "\n"
        "    <h2>Metrics Summary</h2>\n"
        f"    {metrics_table}\n"
        "\n"
        "    <h2>Equity Curve</h2>\n"
        f"    {equity_chart}\n"
        "\n"
        "    <h2>Drawdown</h2>\n"
        f"    {drawdown_chart}\n"
        "\n"
        "    <h2>Monthly Returns</h2>\n"
        f"    {monthly_heatmap}\n"
        "\n"
        "    <h2>Trade Log</h2>\n"
        f"    {trade_log}\n"
        "</body>\n"
        "</html>"
    )
    return html
