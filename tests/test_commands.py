"""Tests for Telegram bot command handlers."""

import datetime

from trading_advisor.notifications.commands import (
    handle_help,
    handle_portfolio,
    handle_risk,
    handle_status,
)
from trading_advisor.portfolio.manager import (
    PortfolioState,
    Position,
    ThrottleState,
)

# ------------------------------------------------------------------
# handle_status tests
# ------------------------------------------------------------------


def test_status_profitable_state() -> None:
    """Status with profitable equity shows correct P&L and drawdown."""
    state = PortfolioState(
        cash=15300.0,
        positions=(),
        high_water_mark=15500.0,
        throttle_state=ThrottleState.NORMAL,
    )
    result = handle_status(state, starting_capital=15000.0)

    assert "+€300.00" in result
    assert "+2.0%" in result
    assert "1.3%" in result
    assert "NORMAL" in result
    assert "15300.00" in result


def test_status_negative_pnl_with_throttle() -> None:
    """Status with loss shows negative P&L, correct drawdown, throttle."""
    state = PortfolioState(
        cash=12000.0,
        positions=(),
        high_water_mark=15000.0,
        throttle_state=ThrottleState.THROTTLED_50,
    )
    result = handle_status(state, starting_capital=15000.0)

    assert "-€3000.00" in result
    assert "-20.0%" in result
    assert "20.0%" in result
    assert "THROTTLED_50" in result


def test_status_zero_hwm_fresh_portfolio() -> None:
    """Status with zero HWM (fresh portfolio) shows 0.0% drawdown."""
    state = PortfolioState(
        cash=15000.0,
        positions=(),
        high_water_mark=0.0,
        throttle_state=ThrottleState.NORMAL,
    )
    result = handle_status(state, starting_capital=15000.0)

    assert "0.0%" in result


# ------------------------------------------------------------------
# handle_portfolio tests
# ------------------------------------------------------------------


def test_portfolio_with_position() -> None:
    """Portfolio with a position shows entry, P&L, days, SL, TP, cash."""
    state = PortfolioState(
        cash=14800.0,
        positions=(
            Position(
                symbol="XAU/USD",
                entry_price=2000.0,
                size=0.1,
                entry_date=datetime.date(2026, 3, 7),
                stop_loss=1960.0,
                take_profit=2100.0,
                signal_atr=20.0,
            ),
        ),
        high_water_mark=15000.0,
        throttle_state=ThrottleState.NORMAL,
    )
    result = handle_portfolio(state, {"XAU/USD": 2050.0}, datetime.date(2026, 3, 10))

    assert "P&L: +€5.00" in result
    assert "Days: 3" in result
    assert "XAU/USD" in result
    assert "2000.00" in result
    assert "0.10" in result
    assert "1960.00" in result
    assert "2100.00" in result
    assert "14800.00" in result


def test_portfolio_negative_unrealized_pnl() -> None:
    """Portfolio with a losing position shows negative P&L."""
    state = PortfolioState(
        cash=14800.0,
        positions=(
            Position(
                symbol="XAU/USD",
                entry_price=2000.0,
                size=0.1,
                entry_date=datetime.date(2026, 3, 7),
                stop_loss=1960.0,
                take_profit=2100.0,
                signal_atr=20.0,
            ),
        ),
        high_water_mark=15000.0,
        throttle_state=ThrottleState.NORMAL,
    )
    result = handle_portfolio(state, {"XAU/USD": 1980.0}, datetime.date(2026, 3, 10))

    assert "P&L: -€2.00" in result


def test_portfolio_no_positions() -> None:
    """Portfolio with no positions shows placeholder and cash."""
    state = PortfolioState(
        cash=15000.0,
        positions=(),
        high_water_mark=15000.0,
        throttle_state=ThrottleState.NORMAL,
    )
    result = handle_portfolio(state, {}, datetime.date(2026, 3, 10))

    assert "No open positions" in result
    assert "15000.00" in result


# ------------------------------------------------------------------
# handle_risk tests
# ------------------------------------------------------------------


def test_risk_with_position() -> None:
    """Risk dashboard with one position shows correct metrics."""
    state = PortfolioState(
        cash=14800.0,
        positions=(
            Position(
                symbol="XAU/USD",
                entry_price=2000.0,
                size=0.1,
                entry_date=datetime.date(2026, 3, 7),
                stop_loss=1960.0,
                take_profit=2100.0,
                signal_atr=20.0,
            ),
        ),
        high_water_mark=15000.0,
        throttle_state=ThrottleState.NORMAL,
    )
    result = handle_risk(state)

    assert "1.3%" in result
    assert "1.4%" in result
    assert "98.7%" in result
    assert "15000.00" in result
    assert "NORMAL" in result


def test_risk_empty_portfolio() -> None:
    """Risk dashboard with no positions shows 0% heat and 100% cash reserve."""
    state = PortfolioState(
        cash=15000.0,
        positions=(),
        high_water_mark=15000.0,
        throttle_state=ThrottleState.NORMAL,
    )
    result = handle_risk(state)

    assert "0.0%" in result
    assert "100.0%" in result


def test_risk_zero_cash_edge() -> None:
    """Risk dashboard with zero cash shows 100% drawdown and handles division guard."""
    state = PortfolioState(
        cash=0.0,
        positions=(),
        high_water_mark=15000.0,
        throttle_state=ThrottleState.HALTED,
    )
    result = handle_risk(state)

    assert "100.0%" in result
    assert "HALTED" in result


# ------------------------------------------------------------------
# handle_help tests
# ------------------------------------------------------------------


def test_help_lists_all_commands() -> None:
    """Help message lists all 8 command names."""
    result = handle_help()

    assert "/status" in result
    assert "/portfolio" in result
    assert "/executed" in result
    assert "/skip" in result
    assert "/close" in result
    assert "/risk" in result
    assert "/resume" in result
    assert "/help" in result
