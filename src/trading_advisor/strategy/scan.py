"""Historical signal scanner — diagnostic tool for spot-checking signals."""

import datetime
from collections.abc import Sequence

import pandas as pd

from trading_advisor.guards.base import Guard
from trading_advisor.guards.pipeline import run_guards
from trading_advisor.indicators.composite import Signal
from trading_advisor.portfolio.manager import ThrottleState
from trading_advisor.strategy.orders import (
    compute_stop_loss,
    compute_take_profit,
    compute_trap_order,
)
from trading_advisor.strategy.sizing import compute_position_size


def scan_signals(
    indicators: pd.DataFrame,
    eurusd: pd.DataFrame,
    guards: Sequence[Guard],
    guards_enabled: dict[str, bool],
    starting_equity: float = 15000.0,
) -> pd.DataFrame:
    """Scan historical data for all dates that would generate a signal.

    This is a diagnostic tool, not the backtest. It evaluates each date
    independently, assuming starting capital and no open positions. Portfolio
    state (drawdown, partial positions) is ignored.

    Args:
        indicators: DataFrame with composite columns (must include: composite,
            signal, high, close, atr_14, adx_14, ema_8). Index is DatetimeIndex.
        eurusd: DataFrame with close and sma_200 columns for EUR/USD.
            Index is DatetimeIndex.
        guards: Ordered sequence of guard instances.
        guards_enabled: Maps guard name to on/off.
        starting_equity: Assumed equity for sizing (default 15000).

    Returns:
        DataFrame with one row per signal date. Columns:
            date, composite, signal, buy_stop, limit, stop_loss, take_profit,
            position_size, risk_amount, risk_reward.
        Empty DataFrame (with correct columns) if no signals found.
    """
    records: list[dict[str, object]] = []

    # Column names for the output
    columns = [
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

    for ts in indicators.index:
        row = indicators.loc[ts]
        signal_str = str(row["signal"])

        # Only BUY / STRONG_BUY proceed
        if signal_str not in (Signal.BUY.value, Signal.STRONG_BUY.value):
            continue

        # Check if EUR/USD data exists for this date
        if ts not in eurusd.index:
            continue

        eurusd_row = eurusd.loc[ts]

        # Convert timestamp to date for EventGuard
        eval_date: datetime.date
        if isinstance(ts, pd.Timestamp):
            eval_date = ts.date()
        else:  # pragma: no cover  # pandas DatetimeIndex always yields pd.Timestamp
            eval_date = datetime.date.fromisoformat(str(ts))

        # Run guards
        guard_kwargs: dict[str, object] = {
            "eurusd_close": float(eurusd_row["close"]),
            "eurusd_sma_200": float(eurusd_row["sma_200"]),
            "adx": float(row["adx_14"]),
            "evaluation_date": eval_date,
            "close": float(row["close"]),
            "ema_8": float(row["ema_8"]),
            "drawdown": 0.0,  # No portfolio state — assume 0% drawdown
        }

        guard_results = run_guards(guards, guards_enabled, **guard_kwargs)
        if not all(gr.passed for gr in guard_results):
            continue

        # Compute trap order
        high = float(row["high"])
        atr = float(row["atr_14"])
        adx = float(row["adx_14"])

        trap = compute_trap_order(high, atr)
        entry = trap.buy_stop

        # Compute exits
        sl = compute_stop_loss(entry, atr)
        tp = compute_take_profit(entry, atr, adx)

        # Compute size (assume starting equity, no positions, NORMAL throttle)
        size = compute_position_size(
            equity=starting_equity,
            cash=starting_equity,
            entry_price=entry,
            atr=atr,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )

        if size == 0.0:
            continue

        risk_per_unit = entry - sl
        risk_amount = size * risk_per_unit
        reward_per_unit = tp - entry
        risk_reward = reward_per_unit / risk_per_unit

        records.append(
            {
                "date": eval_date,
                "composite": float(row["composite"]),
                "signal": signal_str,
                "buy_stop": entry,
                "limit": trap.limit,
                "stop_loss": sl,
                "take_profit": tp,
                "position_size": size,
                "risk_amount": risk_amount,
                "risk_reward": risk_reward,
            }
        )

    if not records:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(records)
