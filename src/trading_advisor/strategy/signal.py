"""TradeSignal frozen dataclass — the output of the signal generation pipeline."""

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class TradeSignal:
    """Immutable value object representing a single trade signal.

    Attributes:
        date: Signal evaluation date.
        asset: Instrument identifier (e.g., "XAU/USD").
        direction: Trade direction — always "LONG" in Phase 1.
        composite_score: Raw composite z-score.
        signal_strength: One of "BUY" or "STRONG_BUY".
        trap_order_stop: Buy stop price.
        trap_order_limit: Limit price above buy stop.
        stop_loss: Fixed stop loss price.
        take_profit: Take profit price.
        trailing_stop_atr_mult: ATR multiplier for trailing stop (always 2.0).
        position_size: Number of lots.
        risk_amount: Dollar risk (size × (entry - SL)).
        risk_reward_ratio: Reward-to-risk ratio.
        guards_passed: Names of guards that passed.
        ttl: Time-to-live in trading days (always 1).
    """

    date: datetime.date
    asset: str
    direction: str
    composite_score: float
    signal_strength: str
    trap_order_stop: float
    trap_order_limit: float
    stop_loss: float
    take_profit: float
    trailing_stop_atr_mult: float
    position_size: float
    risk_amount: float
    risk_reward_ratio: float
    guards_passed: tuple[str, ...]
    ttl: int

    def __post_init__(self) -> None:
        """Validate field invariants after construction.

        Raises:
            ValueError: If any field violates its invariant.
        """
        if self.position_size <= 0:
            raise ValueError("position_size must be positive")
        if self.stop_loss >= self.trap_order_stop:
            raise ValueError("stop_loss must be below trap_order_stop")
        if self.trap_order_stop >= self.take_profit:
            raise ValueError("trap_order_stop must be below take_profit")
        if self.trap_order_limit <= self.trap_order_stop:
            raise ValueError("trap_order_limit must be above trap_order_stop")
        if self.ttl <= 0:
            raise ValueError("ttl must be positive")
        if self.risk_amount <= 0:
            raise ValueError("risk_amount must be positive")
        if self.risk_reward_ratio <= 0:
            raise ValueError("risk_reward_ratio must be positive")
