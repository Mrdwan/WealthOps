"""Trap order entry levels and exit price calculations."""

from typing import NamedTuple


class TrapOrder(NamedTuple):
    """Trap order price levels.

    Attributes:
        buy_stop: Buy-stop trigger price.
        limit: Maximum fill price (cap above buy_stop).
    """

    buy_stop: float
    limit: float


def compute_trap_order(signal_day_high: float, atr: float) -> TrapOrder:
    """Compute trap order entry levels.

    The trap order is a buy-stop with a limit cap, placed for the next
    trading session after a signal fires.

    Args:
        signal_day_high: The high price of the signal day's candle.
        atr: ATR(14) value on the signal day.

    Returns:
        TrapOrder with buy_stop and limit prices.
    """
    buy_stop = signal_day_high + 0.02 * atr
    limit = buy_stop + 0.05 * atr
    return TrapOrder(buy_stop=buy_stop, limit=limit)


def compute_stop_loss(entry_price: float, atr: float) -> float:
    """Compute fixed stop-loss price.

    Stop loss is placed 2x ATR below entry. Never moves after placement.

    Args:
        entry_price: The fill price (buy_stop price).
        atr: ATR(14) value on the signal day.

    Returns:
        Stop-loss price.
    """
    return entry_price - 2.0 * atr


def compute_take_profit(entry_price: float, atr: float, adx: float) -> float:
    """Compute take-profit price with ADX-scaled multiplier.

    Multiplier formula: ``clamp(2 + ADX/30, 2.5, 4.5)``
    TP = entry_price + multiplier × ATR.

    Args:
        entry_price: The fill price (buy_stop price).
        atr: ATR(14) value on the signal day.
        adx: ADX(14) value on the signal day.

    Returns:
        Take-profit price.
    """
    mult = max(2.5, min(4.5, 2.0 + adx / 30.0))
    return entry_price + mult * atr
