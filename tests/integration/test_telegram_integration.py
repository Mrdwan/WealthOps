"""Integration test: full Telegram bot lifecycle.

Scenario:
  1. Create portfolio with starting capital
  2. Generate a trade signal
  3. Save pending signal
  4. Format signal card (verify non-empty)
  5. /executed -- confirm execution, position opens
  6. /status -- verify equity reflects position cost
  7. /portfolio -- verify position shown with unrealized P&L
  8. /close -- close position, verify P&L
  9. Verify state: no positions, cash = initial - cost + proceeds, 1 closed trade
"""

import datetime
from pathlib import Path

from trading_advisor.notifications.commands import (
    handle_close,
    handle_executed,
    handle_portfolio,
    handle_resume,
    handle_skip,
    handle_status,
)
from trading_advisor.notifications.formatters import format_signal_card
from trading_advisor.notifications.signal_store import SignalStore
from trading_advisor.portfolio.manager import PortfolioManager
from trading_advisor.storage.local import LocalStorage
from trading_advisor.strategy.signal import TradeSignal


def _make_signal() -> TradeSignal:
    return TradeSignal(
        date=datetime.date(2026, 3, 10),
        asset="XAU/USD",
        direction="LONG",
        composite_score=1.65,
        signal_strength="BUY",
        trap_order_stop=2000.0,
        trap_order_limit=2001.0,
        stop_loss=1960.0,
        take_profit=2100.0,
        trailing_stop_atr_mult=2.0,
        position_size=0.1,
        risk_amount=4.0,
        risk_reward_ratio=2.5,
        guards_passed=("MacroGate", "TrendGate"),
        ttl=1,
    )


def test_full_lifecycle(tmp_path: Path) -> None:
    """End-to-end: signal -> executed -> status -> portfolio -> close -> verified."""
    storage = LocalStorage(tmp_path)
    manager = PortfolioManager(storage)
    signal_store = SignalStore(storage)

    starting_capital = 15000.0
    manager.update_equity(starting_capital)
    signal = _make_signal()

    # Step 1: Format signal card
    card = format_signal_card(signal)
    assert "BUY Signal" in card
    assert "XAU/USD" in card

    # Step 2: Save pending signal
    signal_store.save_pending(signal)
    assert signal_store.load_pending() is not None

    # Step 3: /executed -- open position at signal entry price
    entry_price = signal.trap_order_stop  # 2000.0
    result = handle_executed(manager, signal_store, "2026-03-10", entry_price)
    assert "Executed" in result
    assert signal_store.load_pending() is None  # signal cleared

    # Step 4: Verify position opened
    state = manager.state
    assert len(state.positions) == 1
    pos = state.positions[0]
    assert pos.symbol == "XAU/USD"
    assert pos.entry_price == entry_price  # 2000.0
    assert pos.size == signal.position_size  # 0.1

    # Step 5: /status -- equity reduced by position cost
    # cost = 0.1 * 2000.0 = 200.0
    # cash = 15000.0 - 200.0 = 14800.0
    status_result = handle_status(state, starting_capital)
    assert "14800.00" in status_result
    # P&L from status perspective (cash-based): 14800 - 15000 = -200
    assert "-\u20ac200.00" in status_result

    # Step 6: /portfolio -- show position with unrealized P&L
    current_price = 2050.0
    today = datetime.date(2026, 3, 13)
    portfolio_result = handle_portfolio(state, {"XAU/USD": current_price}, today)
    assert "XAU/USD" in portfolio_result
    # Unrealized P&L = (2050 - 2000) * 0.1 = 5.00
    assert "P&L: +\u20ac5.00" in portfolio_result
    # Days = (March 13 - March 10) = 3
    assert "Days: 3" in portfolio_result

    # Step 7: /close -- close position
    exit_price = 2050.0
    close_result = handle_close(manager, "XAU/USD", exit_price)
    assert "Closed" in close_result
    # P&L = (2050 - 2000) * 0.1 = 5.00
    assert "+\u20ac5.00" in close_result

    # Step 8: Verify final state
    final_state = manager.state
    assert len(final_state.positions) == 0
    assert len(final_state.closed_trades) == 1
    # Cash = 14800 (after open) + 0.1 * 2050 (proceeds) = 14800 + 205 = 15005
    expected_cash = 15005.0
    assert final_state.cash == expected_cash

    # Verify round-trip P&L consistency
    realized_pnl = (exit_price - entry_price) * signal.position_size  # 5.0
    assert final_state.cash == starting_capital + realized_pnl


def test_skip_and_resume_lifecycle(tmp_path: Path) -> None:
    """Test signal skip + resume from HALTED."""
    storage = LocalStorage(tmp_path)
    manager = PortfolioManager(storage)
    signal_store = SignalStore(storage)

    # Skip flow
    signal = _make_signal()
    signal_store.save_pending(signal)
    result = handle_skip(signal_store, "2026-03-10")
    assert "skipped" in result
    assert signal_store.load_pending() is None

    # Resume flow: set up HALTED state
    state_data: dict[str, object] = {
        "cash": 13500.0,
        "positions": [],
        "high_water_mark": 15000.0,
        "throttle_state": "HALTED",
        "closed_trades": [],
    }
    storage.write_json("state/portfolio", state_data)

    resume_result = handle_resume(manager)
    assert "Resumed" in resume_result
    # DD = (15000-13500)/15000 = 10% -> THROTTLED_50
    assert "THROTTLED_50" in resume_result
