"""Backtest report: performance metrics, equity curve charts, monthly heatmap.

compute_metrics: Sharpe, Sortino, Profit Factor, Max Drawdown, Win Rate, etc.
generate_report: Plotly HTML (Task 6, not implemented yet).
"""

import numpy as np
import pandas as pd

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
