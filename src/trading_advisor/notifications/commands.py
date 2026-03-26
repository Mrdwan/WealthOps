"""Command handlers for the Telegram bot.

All handlers are pure functions: take data in, return response string.
No I/O, no async.
"""

import datetime

from trading_advisor.portfolio.manager import PortfolioState


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
