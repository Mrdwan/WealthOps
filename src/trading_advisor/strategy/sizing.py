"""Dual-constraint position sizing with drawdown throttling and cash reserve.

Sizing = min(ATR-based, Cap-based), then throttle, then cash reserve check.
"""

import math

from trading_advisor.portfolio.manager import ThrottleState


def compute_position_size(
    equity: float,
    cash: float,
    entry_price: float,
    atr: float,
    throttle_state: ThrottleState,
    num_open_positions: int,
) -> float:
    """Compute the position size using dual constraints, throttling, and cash reserve.

    The algorithm applies two constraints (ATR-based and cap-based), takes the
    minimum, then applies drawdown throttling, and finally enforces a cash
    reserve floor. The result is rounded down to the nearest 0.01 lot.

    Args:
        equity: Total portfolio equity value.
        cash: Available cash balance.
        entry_price: Price at which the position would be entered.
        atr: Average True Range of the instrument.
        throttle_state: Current drawdown throttle state.
        num_open_positions: Number of currently open positions.

    Returns:
        The computed position size in lots, rounded down to 0.01.
        Returns 0.0 if the size falls below the minimum lot or is blocked
        by throttle state or cash reserve constraints.
    """
    # Step 1: Determine risk_pct and reserve_pct by equity tier
    if equity < 5000.0:
        risk_pct = 0.01
        reserve_pct = 0.40
    elif equity < 15000.0:
        risk_pct = 0.015
        reserve_pct = 0.30
    else:
        risk_pct = 0.02
        reserve_pct = 0.25

    # Step 2: Compute dual constraint
    atr_based = equity * risk_pct / (atr * 2.0)
    cap_based = equity * 0.15 / entry_price
    size = min(atr_based, cap_based)

    # Step 3: Apply throttle state
    if throttle_state == ThrottleState.HALTED:
        return 0.0
    if throttle_state == ThrottleState.THROTTLED_MAX1:
        if num_open_positions >= 1:
            return 0.0
        size = size / 2.0
    elif throttle_state == ThrottleState.THROTTLED_50:
        size = size / 2.0

    # Step 4: Cash reserve check
    cost = size * entry_price
    remaining = cash - cost
    required_reserve = equity * reserve_pct
    if remaining < required_reserve:
        max_cost = cash - required_reserve
        if max_cost <= 0.0:
            return 0.0
        size = max_cost / entry_price

    # Step 5: Round down to 0.01 minimum lot
    size = math.floor(size * 100.0) / 100.0
    if size < 0.01:
        return 0.0

    return size
