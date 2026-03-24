"""Tests for Portfolio Manager: state machine, persistence, throttle transitions."""

import datetime
from pathlib import Path

import pytest

from trading_advisor.portfolio.manager import (
    PortfolioManager,
    Position,
    ThrottleState,
)
from trading_advisor.storage.local import LocalStorage


@pytest.fixture()
def manager(tmp_path: Path) -> PortfolioManager:
    """Create a PortfolioManager backed by temporary local storage."""
    storage = LocalStorage(tmp_path)
    return PortfolioManager(storage)


# ------------------------------------------------------------------
# Construction + defaults
# ------------------------------------------------------------------


def test_default_state(manager: PortfolioManager) -> None:
    """New manager with empty storage returns default state."""
    state = manager.state
    assert state.cash == 0.0
    assert state.high_water_mark == 0.0
    assert state.throttle_state == ThrottleState.NORMAL
    assert state.positions == ()
    assert state.closed_trades == ()


# ------------------------------------------------------------------
# HWM + drawdown
# ------------------------------------------------------------------


def test_update_equity_sets_hwm(manager: PortfolioManager) -> None:
    """First equity update sets HWM and stays NORMAL."""
    result = manager.update_equity(15000.0)
    assert result == ThrottleState.NORMAL
    assert manager.state.high_water_mark == 15000.0
    assert manager.get_drawdown() == 0.0


def test_hwm_only_ratchets_up(manager: PortfolioManager) -> None:
    """HWM only increases, never decreases."""
    manager.update_equity(15000.0)
    manager.update_equity(14000.0)
    assert manager.state.high_water_mark == 15000.0


def test_drawdown_calculation(manager: PortfolioManager) -> None:
    """DD = (HWM - equity) / HWM = 1500/15000 = 0.10."""
    manager.update_equity(15000.0)
    manager.update_equity(13500.0)
    assert manager.get_drawdown() == pytest.approx(0.10)


# ------------------------------------------------------------------
# Escalation
# ------------------------------------------------------------------


def test_normal_to_throttled_50(manager: PortfolioManager) -> None:
    """DD=8% from NORMAL triggers THROTTLED_50."""
    manager.update_equity(15000.0)
    result = manager.update_equity(13800.0)  # DD = 8%
    assert result == ThrottleState.THROTTLED_50


def test_throttled_50_to_throttled_max1(manager: PortfolioManager) -> None:
    """DD=12% from THROTTLED_50 triggers THROTTLED_MAX1."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    result = manager.update_equity(13200.0)  # DD = 12%
    assert result == ThrottleState.THROTTLED_MAX1


def test_throttled_max1_to_halted(manager: PortfolioManager) -> None:
    """DD=15% from THROTTLED_MAX1 triggers HALTED."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    manager.update_equity(13200.0)  # THROTTLED_MAX1
    result = manager.update_equity(12750.0)  # DD = 15%
    assert result == ThrottleState.HALTED


def test_normal_jumps_to_throttled_max1(manager: PortfolioManager) -> None:
    """DD=12% directly from NORMAL skips THROTTLED_50 to THROTTLED_MAX1."""
    manager.update_equity(15000.0)
    result = manager.update_equity(13200.0)  # DD = 12%
    assert result == ThrottleState.THROTTLED_MAX1


# ------------------------------------------------------------------
# Staying in state (hysteresis)
# ------------------------------------------------------------------


def test_throttled_50_stays_at_7_percent(manager: PortfolioManager) -> None:
    """In THROTTLED_50, DD=7% (>=6%, <8%) stays THROTTLED_50."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    result = manager.update_equity(13950.0)  # DD = 7%
    assert result == ThrottleState.THROTTLED_50


def test_throttled_max1_stays_at_9_percent(manager: PortfolioManager) -> None:
    """In THROTTLED_MAX1, DD=9% (>=8%, <12%) stays THROTTLED_MAX1."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    manager.update_equity(13200.0)  # THROTTLED_MAX1
    result = manager.update_equity(13650.0)  # DD = 9%
    assert result == ThrottleState.THROTTLED_MAX1


# ------------------------------------------------------------------
# Recovery
# ------------------------------------------------------------------


def test_throttled_max1_recovers_to_throttled_50(
    manager: PortfolioManager,
) -> None:
    """In THROTTLED_MAX1, DD=7% (<8%) recovers to THROTTLED_50."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    manager.update_equity(13200.0)  # THROTTLED_MAX1
    result = manager.update_equity(13950.0)  # DD = 7%
    assert result == ThrottleState.THROTTLED_50


def test_throttled_50_recovers_to_normal(manager: PortfolioManager) -> None:
    """In THROTTLED_50, DD=5% (<6%) recovers to NORMAL."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    result = manager.update_equity(14250.0)  # DD = 5%
    assert result == ThrottleState.NORMAL


def test_halted_stays_without_auto_recover(tmp_path: Path) -> None:
    """HALTED stays HALTED when auto_recover=False even with low DD."""
    storage = LocalStorage(tmp_path)
    mgr = PortfolioManager(storage, auto_recover=False)
    mgr.update_equity(15000.0)
    mgr.update_equity(13800.0)  # THROTTLED_50
    mgr.update_equity(13200.0)  # THROTTLED_MAX1
    mgr.update_equity(12750.0)  # HALTED
    result = mgr.update_equity(14250.0)  # DD = 5%
    assert result == ThrottleState.HALTED


def test_halted_auto_recovers_in_backtest(tmp_path: Path) -> None:
    """HALTED auto-recovers to THROTTLED_50 when auto_recover=True and DD<8%."""
    storage = LocalStorage(tmp_path)
    mgr = PortfolioManager(storage, auto_recover=True)
    mgr.update_equity(15000.0)
    mgr.update_equity(13800.0)  # THROTTLED_50
    mgr.update_equity(13200.0)  # THROTTLED_MAX1
    mgr.update_equity(12750.0)  # HALTED
    result = mgr.update_equity(13950.0)  # DD = 7%
    assert result == ThrottleState.THROTTLED_50


# ------------------------------------------------------------------
# Resume
# ------------------------------------------------------------------


def test_resume_to_throttled_max1(manager: PortfolioManager) -> None:
    """HALTED with DD=12% resumes to THROTTLED_MAX1."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    manager.update_equity(13200.0)  # THROTTLED_MAX1
    manager.update_equity(12750.0)  # HALTED
    # Equity stays at 13200 -> DD=12% after update
    manager.update_equity(13200.0)  # still HALTED (no auto_recover)
    result = manager.resume_from_halted()
    assert result == ThrottleState.THROTTLED_MAX1


def test_resume_to_throttled_50(manager: PortfolioManager) -> None:
    """HALTED with DD=7% resumes to THROTTLED_50."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    manager.update_equity(13200.0)  # THROTTLED_MAX1
    manager.update_equity(12750.0)  # HALTED
    manager.update_equity(13950.0)  # DD=7%, still HALTED (no auto_recover)
    result = manager.resume_from_halted()
    assert result == ThrottleState.THROTTLED_50


def test_resume_to_normal(manager: PortfolioManager) -> None:
    """HALTED with DD=4% resumes to NORMAL."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    manager.update_equity(13200.0)  # THROTTLED_MAX1
    manager.update_equity(12750.0)  # HALTED
    manager.update_equity(14400.0)  # DD=4%, still HALTED (no auto_recover)
    result = manager.resume_from_halted()
    assert result == ThrottleState.NORMAL


def test_resume_stays_halted_at_15_percent(manager: PortfolioManager) -> None:
    """HALTED with DD=15% stays HALTED after resume attempt."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50
    manager.update_equity(13200.0)  # THROTTLED_MAX1
    manager.update_equity(12750.0)  # HALTED
    # Equity stays at 12750 -> DD=15%
    result = manager.resume_from_halted()
    assert result == ThrottleState.HALTED


def test_resume_raises_when_not_halted(manager: PortfolioManager) -> None:
    """Resume raises ValueError when not in HALTED state."""
    manager.update_equity(15000.0)
    with pytest.raises(ValueError, match="HALTED"):
        manager.resume_from_halted()


# ------------------------------------------------------------------
# Position operations
# ------------------------------------------------------------------


def test_open_position(manager: PortfolioManager) -> None:
    """Opening a position deducts cost from cash."""
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAUUSD",
        entry_price=2000.0,
        size=0.5,
        entry_date=datetime.date(2024, 6, 1),
        stop_loss=1950.0,
        take_profit=2100.0,
        signal_atr=30.0,
    )
    manager.open_position(pos)
    state = manager.state
    assert state.cash == pytest.approx(14000.0)
    assert len(state.positions) == 1
    assert state.positions[0].symbol == "XAUUSD"


def test_close_position_full(manager: PortfolioManager) -> None:
    """Closing full position returns P&L and removes position."""
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAUUSD",
        entry_price=2000.0,
        size=0.5,
        entry_date=datetime.date(2024, 6, 1),
        stop_loss=1950.0,
        take_profit=2100.0,
        signal_atr=30.0,
    )
    manager.open_position(pos)
    pnl = manager.close_position("XAUUSD", exit_price=2100.0, size=0.5)
    assert pnl == pytest.approx(50.0)
    state = manager.state
    # Cash: 14000 + 0.5 * 2100 = 14000 + 1050 = 15050
    assert state.cash == pytest.approx(15050.0)
    assert len(state.positions) == 0
    assert len(state.closed_trades) == 1


def test_close_position_partial(manager: PortfolioManager) -> None:
    """Partial close reduces size and marks is_partial=True."""
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAUUSD",
        entry_price=2000.0,
        size=1.0,
        entry_date=datetime.date(2024, 6, 1),
        stop_loss=1950.0,
        take_profit=2100.0,
        signal_atr=30.0,
    )
    manager.open_position(pos)
    pnl = manager.close_position("XAUUSD", exit_price=2100.0, size=0.5)
    assert pnl == pytest.approx(50.0)
    state = manager.state
    # Cash: 13000 + 0.5 * 2100 = 13000 + 1050 = 14050
    assert state.cash == pytest.approx(14050.0)
    assert len(state.positions) == 1
    assert state.positions[0].size == pytest.approx(0.5)
    assert state.positions[0].is_partial is True


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------


def test_halted_stays_at_10_percent(manager: PortfolioManager) -> None:
    """HALTED with DD=10% (>=8%, <12%) must stay HALTED."""
    manager.update_equity(15000.0)
    manager.update_equity(13800.0)  # THROTTLED_50 (DD=8%)
    manager.update_equity(13200.0)  # THROTTLED_MAX1 (DD=12%)
    manager.update_equity(12750.0)  # HALTED (DD=15%)
    result = manager.update_equity(13500.0)  # DD=10%, still HALTED
    assert result == ThrottleState.HALTED


# ------------------------------------------------------------------
# close_position validation
# ------------------------------------------------------------------


def test_close_position_zero_size_raises(manager: PortfolioManager) -> None:
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAUUSD",
        entry_price=2000.0,
        size=0.5,
        entry_date=datetime.date(2024, 1, 15),
        stop_loss=1970.0,
        take_profit=2060.0,
        signal_atr=15.0,
    )
    manager.open_position(pos)
    with pytest.raises(ValueError, match="positive"):
        manager.close_position("XAUUSD", exit_price=2100.0, size=0.0)


def test_close_position_oversized_raises(manager: PortfolioManager) -> None:
    manager.update_equity(15000.0)
    pos = Position(
        symbol="XAUUSD",
        entry_price=2000.0,
        size=0.5,
        entry_date=datetime.date(2024, 1, 15),
        stop_loss=1970.0,
        take_profit=2060.0,
        signal_atr=15.0,
    )
    manager.open_position(pos)
    with pytest.raises(ValueError, match="exceeds"):
        manager.close_position("XAUUSD", exit_price=2100.0, size=0.6)


# ------------------------------------------------------------------
# _from_dict validation
# ------------------------------------------------------------------


def test_corrupted_closed_trades_raises(tmp_path: Path) -> None:
    """Non-dict entries in closed_trades must raise, not silently drop."""
    storage = LocalStorage(tmp_path)
    state_data = {
        "cash": 15000.0,
        "positions": [],
        "high_water_mark": 15000.0,
        "throttle_state": "NORMAL",
        "closed_trades": ["not_a_dict"],
    }
    storage.write_json("state/portfolio", state_data)
    mgr = PortfolioManager(storage)
    with pytest.raises(TypeError, match="closed_trades"):
        _ = mgr.state


def test_corrupted_positions_non_list_raises(tmp_path: Path) -> None:
    """Non-list positions field must raise TypeError."""
    storage = LocalStorage(tmp_path)
    state_data: dict[str, object] = {
        "cash": 15000.0,
        "positions": "not_a_list",
        "high_water_mark": 15000.0,
        "throttle_state": "NORMAL",
        "closed_trades": [],
    }
    storage.write_json("state/portfolio", state_data)
    mgr = PortfolioManager(storage)
    with pytest.raises(TypeError, match="positions"):
        _ = mgr.state


def test_corrupted_position_entry_non_dict_raises(tmp_path: Path) -> None:
    """Non-dict entry in positions list must raise TypeError."""
    storage = LocalStorage(tmp_path)
    state_data: dict[str, object] = {
        "cash": 15000.0,
        "positions": ["not_a_dict"],
        "high_water_mark": 15000.0,
        "throttle_state": "NORMAL",
        "closed_trades": [],
    }
    storage.write_json("state/portfolio", state_data)
    mgr = PortfolioManager(storage)
    with pytest.raises(TypeError, match="positions"):
        _ = mgr.state


def test_corrupted_closed_trades_non_list_raises(tmp_path: Path) -> None:
    """Non-list closed_trades field must raise TypeError."""
    storage = LocalStorage(tmp_path)
    state_data: dict[str, object] = {
        "cash": 15000.0,
        "positions": [],
        "high_water_mark": 15000.0,
        "throttle_state": "NORMAL",
        "closed_trades": "not_a_list",
    }
    storage.write_json("state/portfolio", state_data)
    mgr = PortfolioManager(storage)
    with pytest.raises(TypeError, match="closed_trades"):
        _ = mgr.state


def test_close_position_symbol_not_found_raises(manager: PortfolioManager) -> None:
    """close_position raises ValueError when symbol has no open position."""
    manager.update_equity(15000.0)
    with pytest.raises(ValueError, match="No open position"):
        manager.close_position("NONEXISTENT", exit_price=2100.0, size=0.5)


def test_get_drawdown_zero_when_no_hwm(manager: PortfolioManager) -> None:
    """get_drawdown returns 0.0 when high_water_mark is 0 (no equity set)."""
    assert manager.get_drawdown() == 0.0


def test_get_throttle_state_default(manager: PortfolioManager) -> None:
    """get_throttle_state returns NORMAL on fresh manager."""
    assert manager.get_throttle_state() == ThrottleState.NORMAL


def test_close_position_second_in_list(manager: PortfolioManager) -> None:
    """Closing the second of two positions iterates past the first (branch coverage)."""
    manager.update_equity(20000.0)
    pos1 = Position(
        symbol="XAUUSD",
        entry_price=2000.0,
        size=0.5,
        entry_date=datetime.date(2024, 6, 1),
        stop_loss=1950.0,
        take_profit=2100.0,
        signal_atr=30.0,
    )
    pos2 = Position(
        symbol="EURUSD",
        entry_price=1.10,
        size=1.0,
        entry_date=datetime.date(2024, 6, 2),
        stop_loss=1.08,
        take_profit=1.15,
        signal_atr=0.005,
    )
    manager.open_position(pos1)
    manager.open_position(pos2)
    pnl = manager.close_position("EURUSD", exit_price=1.12, size=1.0)
    assert pnl == pytest.approx(0.02)
    state = manager.state
    assert len(state.positions) == 1
    assert state.positions[0].symbol == "XAUUSD"


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------


def test_persistence_roundtrip(tmp_path: Path) -> None:
    """State survives manager recreation with same storage."""
    storage = LocalStorage(tmp_path)
    mgr1 = PortfolioManager(storage)
    mgr1.update_equity(15000.0)
    pos = Position(
        symbol="XAUUSD",
        entry_price=2000.0,
        size=0.5,
        entry_date=datetime.date(2024, 6, 1),
        stop_loss=1950.0,
        take_profit=2100.0,
        signal_atr=30.0,
    )
    mgr1.open_position(pos)

    # New manager, same storage
    mgr2 = PortfolioManager(storage)
    state = mgr2.state
    assert state.cash == pytest.approx(14000.0)
    assert state.high_water_mark == 15000.0
    assert state.throttle_state == ThrottleState.NORMAL
    assert len(state.positions) == 1
    assert state.positions[0].symbol == "XAUUSD"
    assert state.positions[0].entry_date == datetime.date(2024, 6, 1)
