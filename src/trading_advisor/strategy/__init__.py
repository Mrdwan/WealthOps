"""Strategy package: Swing Sniper (composite + guards + trap order + sizing)."""

from trading_advisor.strategy.orders import (
    TrapOrder,
    compute_stop_loss,
    compute_take_profit,
    compute_trap_order,
)
from trading_advisor.strategy.signal import TradeSignal
from trading_advisor.strategy.sizing import compute_position_size
from trading_advisor.strategy.swing_sniper import SwingSniper

__all__ = [
    "SwingSniper",
    "TradeSignal",
    "TrapOrder",
    "compute_position_size",
    "compute_stop_loss",
    "compute_take_profit",
    "compute_trap_order",
]
