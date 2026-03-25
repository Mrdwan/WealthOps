"""Backtest package: execution simulation, walk-forward, Monte Carlo, reports."""

from trading_advisor.backtest.engine import (
    BacktestAccount,
    BacktestParams,
    BacktestResult,
    ExitEvent,
    ExitReason,
    Trade,
    check_fill,
    evaluate_exits,
    run_backtest,
)
from trading_advisor.backtest.report import compute_metrics, generate_report

__all__ = [
    "BacktestAccount",
    "BacktestParams",
    "BacktestResult",
    "ExitEvent",
    "ExitReason",
    "Trade",
    "check_fill",
    "compute_metrics",
    "evaluate_exits",
    "generate_report",
    "run_backtest",
]
