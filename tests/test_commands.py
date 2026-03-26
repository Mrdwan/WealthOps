"""Tests for Telegram bot command handlers."""

import datetime

from trading_advisor.notifications.commands import (
    handle_close,
    handle_executed,
    handle_help,
    handle_portfolio,
    handle_resume,
    handle_risk,
    handle_skip,
    handle_status,
)
from trading_advisor.notifications.signal_store import SignalStore
from trading_advisor.portfolio.manager import (
    PortfolioManager,
    PortfolioState,
    Position,
    ThrottleState,
)
from trading_advisor.storage.local import LocalStorage
from trading_advisor.strategy.signal import TradeSignal


def _make_signal(date: datetime.date | None = None) -> TradeSignal:
    return TradeSignal(
        date=date or datetime.date(2026, 3, 10),
        asset="XAU/USD",
        direction="LONG",
        composite_score=1.65,
        signal_strength="BUY",
        trap_order_stop=2352.40,
        trap_order_limit=2353.85,
        stop_loss=2310.00,
        take_profit=2410.00,
        trailing_stop_atr_mult=2.0,
        position_size=0.05,
        risk_amount=212.00,
        risk_reward_ratio=2.72,
        guards_passed=("MacroGate", "TrendGate"),
        ttl=1,
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


# ------------------------------------------------------------------
# handle_executed tests
# ------------------------------------------------------------------


def test_executed_valid(tmp_path: object) -> None:
    """Valid execution opens position, clears signal, returns success message."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    manager.update_equity(15000.0)
    signal_store = SignalStore(storage)
    signal = _make_signal()
    signal_store.save_pending(signal)

    result = handle_executed(manager, signal_store, "2026-03-10", 2352.40)

    assert "✅ Executed" in result
    assert "XAU/USD" in result
    assert "2352.40" in result
    assert "0.05" in result
    assert "Position opened" in result
    assert len(manager.state.positions) == 1
    assert manager.state.positions[0].entry_price == 2352.40
    assert signal_store.load_pending() is None


def test_executed_no_signal(tmp_path: object) -> None:
    """No pending signal returns error message."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    signal_store = SignalStore(storage)

    result = handle_executed(manager, signal_store, "2026-03-10", 2352.40)

    assert "❌ No pending signal." in result


def test_executed_wrong_date(tmp_path: object) -> None:
    """Wrong date returns error and does not clear the signal."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    signal_store = SignalStore(storage)
    signal_store.save_pending(_make_signal())

    result = handle_executed(manager, signal_store, "2026-03-11", 2352.40)

    assert "❌ No pending signal for 2026-03-11" in result
    assert signal_store.load_pending() is not None


# ------------------------------------------------------------------
# handle_skip tests
# ------------------------------------------------------------------


def test_skip_valid(tmp_path: object) -> None:
    """Valid skip clears signal and returns skipped message."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    signal_store = SignalStore(storage)
    signal_store.save_pending(_make_signal())

    result = handle_skip(signal_store, "2026-03-10")

    assert "⏭️" in result
    assert "2026-03-10" in result
    assert "skipped" in result
    assert signal_store.load_pending() is None


def test_skip_no_signal(tmp_path: object) -> None:
    """No pending signal returns error message."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    signal_store = SignalStore(storage)

    result = handle_skip(signal_store, "2026-03-10")

    assert "❌ No pending signal." in result


def test_skip_wrong_date(tmp_path: object) -> None:
    """Wrong date returns error and does not clear the signal."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    signal_store = SignalStore(storage)
    signal_store.save_pending(_make_signal())

    result = handle_skip(signal_store, "2026-03-11")

    assert "❌ No pending signal for 2026-03-11" in result


# ------------------------------------------------------------------
# handle_close tests
# ------------------------------------------------------------------


def test_close_valid(tmp_path: object) -> None:
    """Valid close returns success with P&L and removes position."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAU/USD",
        entry_price=2000.0,
        size=0.1,
        entry_date=datetime.date(2026, 3, 7),
        stop_loss=1960.0,
        take_profit=2100.0,
        signal_atr=20.0,
    )
    manager.open_position(pos)

    result = handle_close(manager, "XAU/USD", 2050.0)

    assert "✅ Closed" in result
    assert "XAU/USD" in result
    assert "2050.00" in result
    # P&L = (2050 - 2000) * 0.1 = 5.00
    assert "+€5.00" in result
    assert "Trade recorded" in result
    assert len(manager.state.positions) == 0


def test_close_symbol_normalization(tmp_path: object) -> None:
    """Symbol without slash matches stored symbol with slash."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAU/USD",
        entry_price=2000.0,
        size=0.1,
        entry_date=datetime.date(2026, 3, 7),
        stop_loss=1960.0,
        take_profit=2100.0,
        signal_atr=20.0,
    )
    manager.open_position(pos)

    result = handle_close(manager, "XAUUSD", 2050.0)

    assert "✅ Closed" in result
    assert len(manager.state.positions) == 0


def test_close_no_position(tmp_path: object) -> None:
    """No matching position returns error message."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    manager.update_equity(15000.0)

    result = handle_close(manager, "XAU/USD", 2050.0)

    assert "❌ No open position" in result


def test_close_negative_pnl(tmp_path: object) -> None:
    """Negative P&L is formatted with minus sign."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAU/USD",
        entry_price=2000.0,
        size=0.1,
        entry_date=datetime.date(2026, 3, 7),
        stop_loss=1960.0,
        take_profit=2100.0,
        signal_atr=20.0,
    )
    manager.open_position(pos)

    result = handle_close(manager, "XAU/USD", 1950.0)

    # P&L = (1950 - 2000) * 0.1 = -5.00
    assert "-€5.00" in result


def test_close_second_position_matched(tmp_path: object) -> None:
    """Close matches the second position when first does not match symbol."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    manager.update_equity(20000.0)
    pos1 = Position(
        symbol="EUR/USD",
        entry_price=1.10,
        size=1.0,
        entry_date=datetime.date(2026, 3, 7),
        stop_loss=1.09,
        take_profit=1.12,
        signal_atr=0.005,
    )
    pos2 = Position(
        symbol="XAU/USD",
        entry_price=2000.0,
        size=0.1,
        entry_date=datetime.date(2026, 3, 7),
        stop_loss=1960.0,
        take_profit=2100.0,
        signal_atr=20.0,
    )
    manager.open_position(pos1)
    manager.open_position(pos2)

    result = handle_close(manager, "XAU/USD", 2050.0)

    assert "✅ Closed" in result
    assert "XAU/USD" in result
    # EUR/USD still open
    assert len(manager.state.positions) == 1
    assert manager.state.positions[0].symbol == "EUR/USD"


# ------------------------------------------------------------------
# handle_resume tests
# ------------------------------------------------------------------


def test_resume_from_halted(tmp_path: object) -> None:
    """Resume from HALTED with 10% DD transitions to THROTTLED_50."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    state_data = {
        "cash": 13500.0,
        "positions": [],
        "high_water_mark": 15000.0,
        "throttle_state": "HALTED",
        "closed_trades": [],
    }
    storage.write_json("state/portfolio", state_data)

    result = handle_resume(manager)

    assert "✅ Resumed" in result
    assert "HALTED" in result
    # DD = (15000-13500)/15000 = 10% -> THROTTLED_50 (DD >= 8%, < 12%)
    assert "THROTTLED_50" in result


def test_resume_not_halted(tmp_path: object) -> None:
    """Not in HALTED state returns error with current state name."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    manager.update_equity(15000.0)  # NORMAL state

    result = handle_resume(manager)

    assert "❌ Not in HALTED state" in result
    assert "NORMAL" in result


def test_resume_high_dd(tmp_path: object) -> None:
    """Resume from HALTED with 13% DD transitions to THROTTLED_MAX1."""
    storage = LocalStorage(tmp_path)  # type: ignore[arg-type]
    manager = PortfolioManager(storage)
    state_data = {
        "cash": 13050.0,  # DD = (15000-13050)/15000 = 13%
        "positions": [],
        "high_water_mark": 15000.0,
        "throttle_state": "HALTED",
        "closed_trades": [],
    }
    storage.write_json("state/portfolio", state_data)

    result = handle_resume(manager)

    assert "✅ Resumed" in result
    assert "THROTTLED_MAX1" in result
