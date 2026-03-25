"""Backtest engine: simulates trap order execution with realistic costs.

Execution model:
  - Signal fires at EOD (23:00 UTC)
  - Trap order placed for next session (buy stop + limit)
  - If gap-through (high > limit) → NOT filled
  - Stop loss, take profit, trailing stop (Chandelier) on daily close
  - Time stop: 10 trading days
  - Costs: IG spread 0.3pts, slippage 0.1pts, overnight funding

Foundation types implemented in Task 1E.
"""

import datetime
import enum
import math
from dataclasses import dataclass

import pandas as pd

from trading_advisor.portfolio.manager import ThrottleState

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_DD_HALT: float = 0.15
_DD_MAX1: float = 0.12
_DD_THROTTLE: float = 0.08
_DD_RECOVERY_NORMAL: float = 0.06
_TIME_STOP_DAYS: int = 10


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------


class ExitReason(enum.Enum):
    """Reason a position was closed."""

    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_STOP = "TIME_STOP"


# ------------------------------------------------------------------
# Value objects
# ------------------------------------------------------------------


@dataclass(frozen=True)
class Trade:
    """A completed trade record from the backtest.

    Attributes:
        entry_date: Date the position was opened.
        exit_date: Date the position was closed.
        entry_price: Fill price at entry.
        exit_price: Fill price at exit.
        size: Position size in lots.
        direction: Trade direction — always "LONG" in Phase 1.
        pnl: Net P&L after all costs.
        exit_reason: The reason the position was closed.
        days_held: Number of trading days held.
        spread_cost: Cost incurred from the bid-ask spread.
        slippage_cost: Cost incurred from slippage.
        funding_cost: Overnight funding charges accumulated.
    """

    entry_date: datetime.date
    exit_date: datetime.date
    entry_price: float
    exit_price: float
    size: float
    direction: str
    pnl: float
    exit_reason: ExitReason
    days_held: int
    spread_cost: float
    slippage_cost: float
    funding_cost: float


@dataclass(frozen=True)
class ExitEvent:
    """A single exit event during position evaluation.

    Attributes:
        price: Exit price.
        size: Number of lots to close.
        reason: The reason for the exit.
    """

    price: float
    size: float
    reason: ExitReason


@dataclass(frozen=True)
class BacktestResult:
    """Immutable result of a completed backtest run.

    Attributes:
        equity_curve: DataFrame with columns equity, drawdown_pct, throttle_state;
            indexed by DatetimeIndex.
        trades: Tuple of all completed trades.
        start_date: First date of the backtest window.
        end_date: Last date of the backtest window.
        starting_capital: Initial capital in account currency.
    """

    equity_curve: pd.DataFrame
    trades: tuple[Trade, ...]
    start_date: datetime.date
    end_date: datetime.date
    starting_capital: float


# ------------------------------------------------------------------
# Backtest account
# ------------------------------------------------------------------


class BacktestAccount:
    """In-memory account state for the backtest — the backtest equivalent of PortfolioManager.

    Does not use StorageBackend. All state is held in memory and updated
    synchronously during simulation. Uses auto_recover=True semantics for
    throttle state (HALTED auto-recovers when drawdown drops below 8%).

    Args:
        starting_capital: Initial cash balance.
    """

    def __init__(self, starting_capital: float) -> None:
        """Initialise the account with starting capital.

        Args:
            starting_capital: Initial cash balance.
        """
        self._cash: float = starting_capital
        self._equity: float = starting_capital
        self._high_water_mark: float = starting_capital
        self._throttle_state: ThrottleState = ThrottleState.NORMAL

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def cash(self) -> float:
        """Current cash balance."""
        return self._cash

    @property
    def high_water_mark(self) -> float:
        """Highest equity value ever recorded."""
        return self._high_water_mark

    @property
    def drawdown(self) -> float:
        """Current drawdown as a fraction (0.0 to 1.0).

        Computed against the last equity value passed to update_equity.

        Returns:
            Drawdown fraction. Returns 0.0 if HWM is 0.
        """
        if self._high_water_mark == 0.0:
            return 0.0
        return max(0.0, (self._high_water_mark - self._equity) / self._high_water_mark)

    @property
    def throttle_state(self) -> ThrottleState:
        """Current drawdown throttle level."""
        return self._throttle_state

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def open_position(self, notional: float, entry_cost: float) -> None:
        """Deduct notional + entry-side costs from cash.

        Args:
            notional: Position notional value to deduct.
            entry_cost: Entry-side transaction costs (spread, slippage).
        """
        self._cash -= notional
        self._cash -= entry_cost

    def close_position(self, proceeds: float, exit_cost: float) -> None:
        """Add proceeds and deduct exit-side costs.

        Args:
            proceeds: Cash received from closing the position.
            exit_cost: Exit-side transaction costs (spread, slippage).
        """
        self._cash += proceeds
        self._cash -= exit_cost

    def charge_funding(self, amount: float) -> None:
        """Deduct overnight funding from cash.

        Args:
            amount: Funding charge to deduct.
        """
        self._cash -= amount

    def update_equity(self, equity: float) -> ThrottleState:
        """Update HWM, drawdown, and throttle state. Returns new throttle state.

        Uses the same escalation/recovery logic as PortfolioManager with
        auto_recover=True:
        - DD >= 15% → HALTED
        - DD >= 12% → THROTTLED_MAX1 (unless already HALTED)
        - DD >= 8% → THROTTLED_50 (unless already in higher state)
        - DD < 8%: HALTED→THROTTLED_50 (auto-recover), MAX1→THROTTLED_50,
          THROTTLED_50→NORMAL only if DD < 6%

        Args:
            equity: Current portfolio equity value.

        Returns:
            The new ThrottleState after evaluation.
        """
        self._equity = equity
        self._high_water_mark = max(self._high_water_mark, equity)
        dd = (
            (self._high_water_mark - equity) / self._high_water_mark
            if self._high_water_mark > 0.0
            else 0.0
        )
        self._throttle_state = self._evaluate_throttle(self._throttle_state, dd)
        return self._throttle_state

    def _evaluate_throttle(self, current: ThrottleState, dd: float) -> ThrottleState:
        """Evaluate next throttle state given current state and drawdown.

        Mirrors PortfolioManager._evaluate_throttle with auto_recover=True.

        Args:
            current: Current throttle state.
            dd: Current drawdown as a fraction.

        Returns:
            The next throttle state.
        """
        # Escalation: always applies regardless of current state
        if dd >= _DD_HALT:
            return ThrottleState.HALTED
        if dd >= _DD_MAX1:
            # HALTED is more severe; only manual resume (or auto-recover) can exit it
            if current == ThrottleState.HALTED:
                return ThrottleState.HALTED
            return ThrottleState.THROTTLED_MAX1
        if dd >= _DD_THROTTLE:
            # If already in a higher state, stay there
            if current == ThrottleState.THROTTLED_MAX1:
                return ThrottleState.THROTTLED_MAX1
            if current == ThrottleState.HALTED:
                return ThrottleState.HALTED
            return ThrottleState.THROTTLED_50

        # Recovery (dd < 0.08) — auto_recover=True always
        if current == ThrottleState.HALTED:
            return ThrottleState.THROTTLED_50
        if current == ThrottleState.THROTTLED_MAX1:
            return ThrottleState.THROTTLED_50
        if current == ThrottleState.THROTTLED_50:
            if dd < _DD_RECOVERY_NORMAL:
                return ThrottleState.NORMAL
            return ThrottleState.THROTTLED_50
        return ThrottleState.NORMAL


# ------------------------------------------------------------------
# Private order / position dataclasses
# ------------------------------------------------------------------


@dataclass(frozen=True)
class _PendingOrder:
    """A trap order awaiting fill.

    Attributes:
        buy_stop: Buy-stop trigger price.
        limit: Maximum fill price (cap above buy_stop).
        signal_atr: ATR value at signal time.
        signal_adx: ADX value at signal time.
        signal_date: Date the signal was generated.
    """

    buy_stop: float
    limit: float
    signal_atr: float
    signal_adx: float
    signal_date: datetime.date


@dataclass
class _ActivePosition:
    """A live position being tracked during the simulation.

    Attributes:
        entry_price: Price at which the position was filled.
        entry_date: Date the position was entered.
        size: Current position size in lots.
        original_size: Position size before any partial closes.
        stop_loss: Current stop-loss price.
        take_profit: Take-profit price.
        signal_atr: ATR value at signal time.
        tp_50_hit: True if the 50% take-profit target has been hit.
        highest_high: Highest high since entry (for trailing stops).
        trailing_stop: Current trailing stop price.
        days_held: Number of days the position has been open.
        cumulative_funding: Total funding charges deducted so far.
    """

    entry_price: float
    entry_date: datetime.date
    size: float
    original_size: float
    stop_loss: float
    take_profit: float
    signal_atr: float
    tp_50_hit: bool
    highest_high: float
    trailing_stop: float
    days_held: int
    cumulative_funding: float


# ------------------------------------------------------------------
# Fill logic
# ------------------------------------------------------------------


def check_fill(buy_stop: float, limit: float, day_high: float, day_low: float) -> bool:
    """Check if a trap order fills on the given day's candle.

    Fill condition: day_high >= buy_stop AND day_low <= limit.
    Gap-throughs are rejected naturally (if price gaps past limit,
    day_low > limit fails).

    Args:
        buy_stop: Buy-stop trigger price.
        limit: Maximum fill price (cap above buy_stop).
        day_high: High price of the day.
        day_low: Low price of the day.

    Returns:
        True if the order fills.
    """
    return day_high >= buy_stop and day_low <= limit


# ------------------------------------------------------------------
# Exit evaluation
# ------------------------------------------------------------------


def evaluate_exits(
    position: _ActivePosition,
    day_high: float,
    day_low: float,
    day_close: float,
) -> list[ExitEvent]:
    """Evaluate all exit conditions for an open position.

    Exit priority (highest to lowest):
      1. Stop loss -- triggers on day_low <= stop_loss
      2. Take profit -- triggers on day_high >= take_profit (50% close)
      3. Trailing stop -- triggers on day_low <= trailing_stop (post-TP only)
      4. Time stop -- triggers when days_held >= 10 trading days

    When SL and TP trigger on the same candle, SL wins (conservative).
    When trailing and time stop trigger on the same candle, trailing wins.
    TP does NOT trigger trailing on the same candle -- trailing begins next day.

    The half-size for TP is: math.floor(position.size / 2 * 100) / 100
    (rounded down to nearest 0.01 lot).

    IMPORTANT: This function does NOT update the position state (tp_50_hit,
    trailing_stop, highest_high). The caller (main loop) is responsible for
    applying state changes after processing exit events.

    Args:
        position: The active position to evaluate.
        day_high: Day's high price.
        day_low: Day's low price.
        day_close: Day's closing price.

    Returns:
        List of ExitEvent objects. Can be empty (no exit), or contain
        1 event (full exit) or 1 event (partial TP exit).
    """
    if not position.tp_50_hit:
        # Pre-TP state: full position at risk
        if day_low <= position.stop_loss:
            return [ExitEvent(position.stop_loss, position.size, ExitReason.STOP_LOSS)]
        if day_high >= position.take_profit:
            half = math.floor(position.size / 2 * 100) / 100
            if half <= 0:
                # Position too small to split -- close entire at TP
                return [ExitEvent(position.take_profit, position.size, ExitReason.TAKE_PROFIT)]
            return [ExitEvent(position.take_profit, half, ExitReason.TAKE_PROFIT)]
        if position.days_held >= _TIME_STOP_DAYS:
            return [ExitEvent(day_close, position.size, ExitReason.TIME_STOP)]
        return []

    # Post-TP state: remaining position with trailing stop
    if day_low <= position.stop_loss:
        return [ExitEvent(position.stop_loss, position.size, ExitReason.STOP_LOSS)]
    if position.trailing_stop > 0 and day_low <= position.trailing_stop:
        return [ExitEvent(position.trailing_stop, position.size, ExitReason.TRAILING_STOP)]
    if position.days_held >= _TIME_STOP_DAYS:
        return [ExitEvent(day_close, position.size, ExitReason.TIME_STOP)]
    return []


# ------------------------------------------------------------------
# Cost model
# ------------------------------------------------------------------


_IG_ADMIN_FEE: float = 0.025  # 2.5% annualized IG admin charge for longs


def compute_round_trip_cost(
    size: float,
    spread_per_side: float,
    slippage_per_side: float,
) -> tuple[float, float]:
    """Compute spread and slippage costs for a full round trip.

    Both entry-side and exit-side costs are included.

    Args:
        size: Position size in lots.
        spread_per_side: Spread cost per side in points.
        slippage_per_side: Slippage cost per side in points.

    Returns:
        Tuple of (spread_cost, slippage_cost).
    """
    spread_cost = 2 * spread_per_side * size
    slippage_cost = 2 * slippage_per_side * size
    return spread_cost, slippage_cost


def compute_overnight_funding(
    position_notional: float,
    fedfunds_rate: float,
) -> float:
    """Compute one night's funding charge for a long spread-bet position.

    Uses the IG formula: notional × (FEDFUNDS + 2.5%) / 365.

    Args:
        position_notional: entry_price × size.
        fedfunds_rate: Annualized Federal Funds rate as a decimal (e.g. 0.05).

    Returns:
        Funding charge for one night.
    """
    return position_notional * (fedfunds_rate + _IG_ADMIN_FEE) / 365


def get_fedfunds_rate(fedfunds: pd.Series, date: pd.Timestamp) -> float:
    """Look up the FEDFUNDS rate for a given date.

    Uses forward-fill semantics: if the exact date is not in the series,
    uses the most recent prior value. If no prior value exists, returns 0.0.

    Args:
        fedfunds: Series indexed by DatetimeIndex with annualized rates.
        date: The date to look up.

    Returns:
        The FEDFUNDS rate as a decimal.
    """
    if fedfunds.empty:
        return 0.0
    # Reindex to include the target date, forward-fill, then look up
    mask = fedfunds.index <= date
    if not mask.any():
        return 0.0
    return float(fedfunds.loc[mask].iloc[-1])
