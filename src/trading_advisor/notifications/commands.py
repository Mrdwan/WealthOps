"""Command handlers for the Telegram bot.

All handlers are pure functions: take data in, return response string.
No I/O, no async.
"""

import datetime

from trading_advisor.notifications.signal_store import SignalStore
from trading_advisor.portfolio.manager import (
    PortfolioManager,
    PortfolioState,
    Position,
    ThrottleState,
)


def handle_status(state: PortfolioState, starting_capital: float) -> str:
    """Format /status response: equity, P&L, drawdown, throttle.

    Args:
        state: Current portfolio snapshot.
        starting_capital: Initial capital for P&L calculation.

    Returns:
        A multi-line string suitable for Telegram delivery.
    """
    cash = state.cash
    pnl = cash - starting_capital
    pnl_pct = (pnl / starting_capital * 100) if starting_capital != 0.0 else 0.0

    hwm = state.high_water_mark
    dd_pct = max(0.0, (hwm - cash) / hwm * 100) if hwm > 0.0 else 0.0

    pnl_str = f"+€{pnl:.2f}" if pnl >= 0.0 else f"-€{abs(pnl):.2f}"
    pnl_pct_str = f"+{pnl_pct:.1f}%" if pnl_pct >= 0.0 else f"-{abs(pnl_pct):.1f}%"

    return (
        "📊 Status\n"
        "\n"
        f"Equity:    €{cash:.2f}\n"
        f"P&L:       {pnl_str} ({pnl_pct_str})\n"
        f"Drawdown:  {dd_pct:.1f}%\n"
        f"Throttle:  {state.throttle_state.value}"
    )


def handle_portfolio(
    state: PortfolioState,
    current_prices: dict[str, float],
    today: datetime.date,
) -> str:
    """Format /portfolio response: positions, unrealized P&L, cash.

    Args:
        state: Current portfolio snapshot.
        current_prices: Mapping of symbol to latest close price.
        today: Today's date for calculating days held.

    Returns:
        A multi-line string suitable for Telegram delivery.
    """
    lines = ["📋 Portfolio", ""]

    if state.positions:
        for pos in state.positions:
            unrealized = (current_prices[pos.symbol] - pos.entry_price) * pos.size
            days = (today - pos.entry_date).days

            pnl_str = f"+€{unrealized:.2f}" if unrealized >= 0.0 else f"-€{abs(unrealized):.2f}"

            lines.append(f"{pos.symbol} LONG")
            lines.append(f"  Entry: {pos.entry_price:.2f} | Size: {pos.size:.2f}")
            lines.append(f"  P&L: {pnl_str} | Days: {days}")
            lines.append(f"  SL: {pos.stop_loss:.2f} | TP: {pos.take_profit:.2f}")
            lines.append("")
    else:
        lines.append("No open positions.")
        lines.append("")

    lines.append(f"Cash: €{state.cash:.2f}")
    return "\n".join(lines)


def handle_risk(state: PortfolioState) -> str:
    """Format /risk response: drawdown, throttle, heat, cash reserve.

    Args:
        state: Current portfolio snapshot.

    Returns:
        A multi-line string suitable for Telegram delivery.
    """
    cash = state.cash
    hwm = state.high_water_mark
    positions = state.positions

    dd_pct = max(0.0, (hwm - cash) / hwm * 100) if hwm > 0.0 else 0.0

    position_value = sum(p.size * p.entry_price for p in positions)

    heat_pct = (position_value / cash * 100) if cash > 0.0 else 0.0

    total = cash + position_value
    reserve_pct = (cash / total * 100) if total > 0.0 else 100.0

    return (
        "⚠️ Risk Dashboard\n"
        "\n"
        f"Drawdown:     {dd_pct:.1f}%\n"
        f"Throttle:     {state.throttle_state.value}\n"
        f"Positions:    {len(positions)}\n"
        f"Heat:         {heat_pct:.1f}%\n"
        f"Cash Reserve: {reserve_pct:.1f}%\n"
        f"HWM:          €{hwm:.2f}"
    )


def handle_help() -> str:
    """Format /help response: list all commands.

    Returns:
        A static multi-line string listing all available commands.
    """
    return (
        "📖 WealthOps Commands\n"
        "\n"
        "/status    — equity, P&L, drawdown, throttle\n"
        "/portfolio — positions, unrealized P&L\n"
        "/executed <date> [price] — confirm trade execution\n"
        "/skip <date> — skip a signal\n"
        "/close <symbol> [price] — close a position\n"
        "/risk      — risk dashboard\n"
        "/resume    — resume from HALTED\n"
        "/help      — this message"
    )


def handle_executed(
    manager: PortfolioManager,
    signal_store: SignalStore,
    signal_date: str,
    execution_price: float,
) -> str:
    """Confirm trade execution: open a position from the pending signal.

    Args:
        manager: Portfolio manager to record the opened position.
        signal_store: Store holding the pending signal.
        signal_date: ISO date string the signal was issued on (e.g. "2026-03-10").
        execution_price: Actual fill price of the trade.

    Returns:
        A multi-line string confirming execution or describing the error.
    """
    signal = signal_store.load_pending()
    if signal is None:
        return "❌ No pending signal."
    if signal.date.isoformat() != signal_date:
        return f"❌ No pending signal for {signal_date}."

    signal_atr = (signal.trap_order_stop - signal.stop_loss) / 2.0
    position = Position(
        symbol=signal.asset,
        entry_price=execution_price,
        size=signal.position_size,
        entry_date=signal.date,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        signal_atr=signal_atr,
    )
    manager.open_position(position)
    signal_store.clear_pending()

    return (
        f"✅ Executed: {signal.asset} {signal.direction}\n"
        "\n"
        f"Entry:  {execution_price:.2f}\n"
        f"Size:   {signal.position_size:.2f} lots\n"
        f"SL:     {signal.stop_loss:.2f}\n"
        f"TP:     {signal.take_profit:.2f}\n"
        f"Risk:   €{signal.risk_amount:.2f}\n"
        "\n"
        "Position opened."
    )


def handle_skip(signal_store: SignalStore, signal_date: str) -> str:
    """Skip a pending signal without executing it.

    Args:
        signal_store: Store holding the pending signal.
        signal_date: ISO date string identifying the signal to skip.

    Returns:
        A confirmation string or an error message.
    """
    signal = signal_store.load_pending()
    if signal is None:
        return "❌ No pending signal."
    if signal.date.isoformat() != signal_date:
        return f"❌ No pending signal for {signal_date}."

    signal_store.clear_pending()
    return f"⏭️ Signal for {signal_date} skipped."


def handle_close(
    manager: PortfolioManager,
    symbol: str,
    exit_price: float,
) -> str:
    """Close an open position and record the realized P&L.

    Symbol matching is slash-insensitive (e.g. "XAUUSD" matches "XAU/USD").

    Args:
        manager: Portfolio manager holding the open positions.
        symbol: Instrument identifier (with or without slash).
        exit_price: Price at which the position is closed.

    Returns:
        A multi-line string showing entry, exit, P&L, or an error message.
    """
    normalized = symbol.replace("/", "")
    state = manager.state
    match: Position | None = None
    for pos in state.positions:
        if pos.symbol.replace("/", "") == normalized:
            match = pos
            break

    if match is None:
        return f"❌ No open position for {symbol}."

    pnl = manager.close_position(match.symbol, exit_price, match.size)
    pnl_str = f"+€{pnl:.2f}" if pnl >= 0 else f"-€{abs(pnl):.2f}"

    return (
        f"✅ Closed: {match.symbol}\n"
        "\n"
        f"Entry:  {match.entry_price:.2f}\n"
        f"Exit:   {exit_price:.2f}\n"
        f"P&L:    {pnl_str}\n"
        "\n"
        "Trade recorded."
    )


def handle_resume(manager: PortfolioManager) -> str:
    """Manually resume trading from HALTED state.

    Args:
        manager: Portfolio manager currently in HALTED state.

    Returns:
        A multi-line string confirming the new state, or an error if not HALTED.
    """
    state = manager.state
    if state.throttle_state != ThrottleState.HALTED:
        return f"❌ Not in HALTED state. Current: {state.throttle_state.value}"

    new_state = manager.resume_from_halted()
    dd = manager.get_drawdown() * 100

    return f"✅ Resumed trading.\n\nPrevious: HALTED\nCurrent:  {new_state.value} (DD: {dd:.1f}%)"
