"""SwingSniper strategy: composite threshold -> guard pipeline -> trap order -> sizing."""

import datetime
from collections.abc import Sequence
from typing import cast

import pandas as pd

from trading_advisor.guards.base import Guard
from trading_advisor.guards.pipeline import run_guards
from trading_advisor.indicators.composite import Signal
from trading_advisor.portfolio.manager import PortfolioManager
from trading_advisor.strategy.base import Strategy
from trading_advisor.strategy.orders import (
    compute_stop_loss,
    compute_take_profit,
    compute_trap_order,
)
from trading_advisor.strategy.signal import TradeSignal
from trading_advisor.strategy.sizing import compute_position_size

_TRAILING_STOP_ATR_MULT: float = 2.0
_TTL: int = 1
_ASSET: str = "XAU/USD"


class SwingSniper(Strategy):
    """Momentum-based swing trading strategy for XAU/USD.

    Evaluates the momentum composite score, checks safety guards,
    computes trap order levels and position size, and produces a
    TradeSignal if all conditions are met.

    Args:
        portfolio: Portfolio manager for state queries.
        guards: Ordered sequence of guard instances.
        guards_enabled: Maps guard name to on/off.
    """

    def __init__(
        self,
        portfolio: PortfolioManager,
        guards: Sequence[Guard],
        guards_enabled: dict[str, bool],
    ) -> None:
        self._portfolio = portfolio
        self._guards = guards
        self._guards_enabled = guards_enabled

    def generate_signals(self, **kwargs: object) -> list[object]:
        """Generate trade signals from market data.

        Required kwargs:
            indicators: pd.DataFrame -- must include columns: composite,
                signal, high, close, atr_14, adx_14, ema_8.
                Index must be a DatetimeIndex.
            eurusd: pd.DataFrame -- must include columns: close, sma_200.
                Index must be a DatetimeIndex.
            evaluation_date: datetime.date -- the date to evaluate.

        Returns:
            List containing zero or one TradeSignal.
        """
        indicators = cast(pd.DataFrame, kwargs["indicators"])
        eurusd = cast(pd.DataFrame, kwargs["eurusd"])
        evaluation_date = cast(datetime.date, kwargs["evaluation_date"])
        result = self._evaluate(indicators, eurusd, evaluation_date)
        if result is None:
            return []
        return [result]

    def _evaluate(
        self,
        indicators: pd.DataFrame,
        eurusd: pd.DataFrame,
        evaluation_date: datetime.date,
    ) -> TradeSignal | None:
        """Internal typed signal evaluation.

        Args:
            indicators: DataFrame with composite and technical indicator columns.
            eurusd: DataFrame with EUR/USD close and sma_200 columns.
            evaluation_date: Date to evaluate.

        Returns:
            A TradeSignal if all conditions met, otherwise None.
        """
        # Convert date to timestamp for DataFrame indexing
        ts = pd.Timestamp(evaluation_date)
        if ts not in indicators.index:
            return None

        row = indicators.loc[ts]
        signal_str = str(row["signal"])

        # Step 1: Check composite threshold -- only BUY / STRONG_BUY proceed
        if signal_str not in (Signal.BUY.value, Signal.STRONG_BUY.value):
            return None

        # Step 2: Partial position rule -- block if any position is open
        state = self._portfolio.state
        if len(state.positions) > 0:
            return None

        # Step 3: Run guards
        # Get EUR/USD data for the evaluation date
        eurusd_row = eurusd.loc[ts]

        guard_kwargs: dict[str, object] = {
            "eurusd_close": float(eurusd_row["close"]),
            "eurusd_sma_200": float(eurusd_row["sma_200"]),
            "adx": float(row["adx_14"]),
            "evaluation_date": evaluation_date,
            "close": float(row["close"]),
            "ema_8": float(row["ema_8"]),
            "drawdown": self._portfolio.get_drawdown(),
        }

        guard_results = run_guards(self._guards, self._guards_enabled, **guard_kwargs)

        if not all(gr.passed for gr in guard_results):
            return None

        guards_passed = tuple(gr.guard_name for gr in guard_results)

        # Step 4: Compute trap order
        signal_day_high = float(row["high"])
        atr = float(row["atr_14"])
        adx = float(row["adx_14"])

        trap = compute_trap_order(signal_day_high, atr)
        entry_price = trap.buy_stop

        # Step 5: Compute exits
        stop_loss = compute_stop_loss(entry_price, atr)
        take_profit = compute_take_profit(entry_price, atr, adx)

        # Step 6: Compute position size
        equity = state.cash  # equity = cash + unrealized P&L; no positions = cash
        # With no positions open (checked in Step 2), equity == cash
        size = compute_position_size(
            equity=equity,
            cash=state.cash,
            entry_price=entry_price,
            atr=atr,
            throttle_state=state.throttle_state,
            num_open_positions=len(state.positions),
        )

        if size == 0.0:
            return None

        # Step 7: Compute derived fields
        risk_per_unit = entry_price - stop_loss
        risk_amount = size * risk_per_unit
        reward_per_unit = take_profit - entry_price
        risk_reward_ratio = reward_per_unit / risk_per_unit

        composite_score = float(row["composite"])

        return TradeSignal(
            date=evaluation_date,
            asset=_ASSET,
            direction="LONG",
            composite_score=composite_score,
            signal_strength=signal_str,
            trap_order_stop=trap.buy_stop,
            trap_order_limit=trap.limit,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_atr_mult=_TRAILING_STOP_ATR_MULT,
            position_size=size,
            risk_amount=risk_amount,
            risk_reward_ratio=risk_reward_ratio,
            guards_passed=guards_passed,
            ttl=_TTL,
        )
