"""Pure formatting functions for Telegram notifications.

Converts structured trade data into plain-text strings with Unicode emojis.
No I/O, no async, no Telegram dependency.
"""

import datetime
from dataclasses import dataclass

from trading_advisor.portfolio.manager import PortfolioState
from trading_advisor.strategy.signal import TradeSignal

# ------------------------------------------------------------------
# Value objects
# ------------------------------------------------------------------


@dataclass(frozen=True)
class BriefingData:
    """Data bundle for daily briefing formatting.

    Attributes:
        date: Briefing date.
        portfolio_state: Current portfolio snapshot.
        equity: Total equity (cash + position market values).
        starting_capital: Initial capital for P&L calculation.
        current_prices: Symbol to latest close price mapping.
        composite_score: Latest momentum composite z-score.
        signal_class: Signal classification string.
        pending_signal: Pending trade signal, if any.
    """

    date: datetime.date
    portfolio_state: PortfolioState
    equity: float
    starting_capital: float
    current_prices: dict[str, float]
    composite_score: float
    signal_class: str
    pending_signal: TradeSignal | None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _fmt_composite(score: float, decimals: int = 2) -> str:
    """Format a composite z-score with sign prefix and sigma symbol.

    Args:
        score: The composite z-score value.
        decimals: Number of decimal places to display.

    Returns:
        Formatted string like '+1.20σ' or '-0.50σ'.
    """
    sign = "+" if score >= 0 else ""
    return f"{sign}{score:.{decimals}f}σ"


def _fmt_money(amount: float) -> str:
    """Format a monetary value with Euro prefix.

    Args:
        amount: The monetary amount.

    Returns:
        Formatted string like '€1234.00'.
    """
    return f"€{amount:.2f}"


def _fmt_pnl_money(amount: float) -> str:
    """Format a P&L amount with sign and Euro prefix.

    Args:
        amount: The P&L amount (may be negative).

    Returns:
        Formatted string like '+€5.00' or '-€10.00'.
    """
    if amount >= 0:
        return f"+€{amount:.2f}"
    return f"-€{abs(amount):.2f}"


def _fmt_pnl_pct(pct: float) -> str:
    """Format a P&L percentage with sign.

    Args:
        pct: Percentage value (already multiplied by 100).

    Returns:
        Formatted string like '+0.0%' or '-6.7%'.
    """
    if pct >= 0:
        return f"+{pct:.1f}%"
    return f"-{abs(pct):.1f}%"


# ------------------------------------------------------------------
# Public formatters
# ------------------------------------------------------------------


def format_signal_card(signal: TradeSignal) -> str:
    """Format a trade signal as a multi-line plain text card.

    Args:
        signal: The trade signal to format.

    Returns:
        A multi-line string suitable for Telegram message delivery.
    """
    label = signal.signal_strength.replace("_", " ")
    ttl_unit = "trading day" if signal.ttl == 1 else "trading days"
    guards_str = ", ".join(signal.guards_passed)
    composite_str = _fmt_composite(signal.composite_score)

    lines = [
        f"🟢 {label} Signal — {signal.asset}",
        "",
        f"📊 Composite: {composite_str}",
        f"📅 Date: {signal.date}",
        "",
        "🎯 Entry",
        f"  Buy Stop: {signal.trap_order_stop:.2f}",
        f"  Limit:    {signal.trap_order_limit:.2f}",
        "",
        "🛑 Risk Management",
        f"  Stop Loss:   {signal.stop_loss:.2f}",
        f"  Take Profit: {signal.take_profit:.2f}",
        f"  Trail:       {signal.trailing_stop_atr_mult}× ATR (after TP)",
        "",
        "📐 Position",
        f"  Size: {signal.position_size} lots",
        f"  Risk: €{signal.risk_amount:.2f}",
        f"  R:R:  {signal.risk_reward_ratio:.2f}",
        "",
        f"✅ Guards: {guards_str}",
        "",
        f"⏰ Valid: {signal.ttl} {ttl_unit}",
    ]
    return "\n".join(lines)


def format_daily_briefing(data: BriefingData) -> str:
    """Format a daily portfolio briefing as a multi-line plain text message.

    Args:
        data: The briefing data bundle to format.

    Returns:
        A multi-line string suitable for Telegram message delivery.
    """
    ps = data.portfolio_state

    # P&L
    pnl = data.equity - data.starting_capital
    pnl_pct = (pnl / data.starting_capital) * 100 if data.starting_capital != 0 else 0.0

    # Drawdown: use equity (cash + unrealized P&L) for accuracy when positions are open
    hwm = ps.high_water_mark
    dd_pct = max(0.0, (hwm - data.equity) / hwm * 100) if hwm > 0.0 else 0.0

    # Composite
    composite_str = _fmt_composite(data.composite_score)

    lines: list[str] = [
        f"📋 Daily Briefing — {data.date}",
        "",
        "💰 Portfolio",
        f"  Equity: {_fmt_money(data.equity)}",
        f"  Cash:   {_fmt_money(ps.cash)}",
        f"  P&L:    {_fmt_pnl_money(pnl)} ({_fmt_pnl_pct(pnl_pct)})",
        "",
        "📊 Open Positions",
    ]

    if ps.positions:
        for pos in ps.positions:
            unrealized = (data.current_prices[pos.symbol] - pos.entry_price) * pos.size
            days_held = (data.date - pos.entry_date).days
            lines.append(f"  {pos.symbol} LONG")
            lines.append(f"    Entry: {pos.entry_price:.2f} | Size: {pos.size}")
            lines.append(f"    P&L: {_fmt_pnl_money(unrealized)} | Days: {days_held}")
            lines.append(f"    SL: {pos.stop_loss:.2f} | TP: {pos.take_profit:.2f}")
    else:
        lines.append("  None")

    lines += [
        "",
        "⚠️ Risk",
        f"  Drawdown: {dd_pct:.1f}% | Throttle: {ps.throttle_state.value}",
        "",
        "📈 Market",
        f"  Composite: {composite_str} ({data.signal_class})",
        "",
    ]

    # Signal line
    if data.pending_signal is not None:
        lines.append("Pending signal — see signal card.")
    elif not ps.positions:
        lines.append("No signal today. Cash is a position. 💤")
    else:
        lines.append("No signal today.")

    return "\n".join(lines)


def format_heartbeat(
    command: str,
    timestamp: datetime.datetime,
    duration_s: float,
    composite: float,
    signal_class: str,
) -> str:
    """Format a heartbeat status line for command confirmations.

    Args:
        command: The command name (e.g., 'ingest', 'briefing').
        timestamp: UTC timestamp of the command execution.
        duration_s: Execution duration in seconds.
        composite: Latest composite z-score.
        signal_class: Signal classification string.

    Returns:
        A single-line status string.
    """
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M")
    return (
        f"✓ {command} {date_str} {time_str} UTC"
        f" — {duration_s:.1f}s"
        f" — XAU composite: {composite:.1f}σ {signal_class}"
    )
