"""Tests for SignalStore — pending trade signal persistence."""

import datetime
from pathlib import Path

import pytest

from trading_advisor.notifications.signal_store import SignalStore
from trading_advisor.storage.local import LocalStorage
from trading_advisor.strategy.signal import TradeSignal

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_signal(date: datetime.date | None = None) -> TradeSignal:
    """Build a canonical test TradeSignal.

    Args:
        date: Override the signal date (defaults to 2026-03-10).

    Returns:
        A fully populated TradeSignal.
    """
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
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> SignalStore:
    """Return a SignalStore backed by a temporary LocalStorage.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        A fresh SignalStore instance.
    """
    storage = LocalStorage(tmp_path)
    return SignalStore(storage)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_save_and_load(store: SignalStore) -> None:
    """Saving a signal then loading it should return an equal signal."""
    signal = _make_signal()
    store.save_pending(signal)
    loaded = store.load_pending()

    assert loaded is not None
    assert loaded.date == signal.date
    assert loaded.asset == signal.asset
    assert loaded.direction == signal.direction
    assert loaded.composite_score == signal.composite_score
    assert loaded.signal_strength == signal.signal_strength
    assert loaded.trap_order_stop == signal.trap_order_stop
    assert loaded.trap_order_limit == signal.trap_order_limit
    assert loaded.stop_loss == signal.stop_loss
    assert loaded.take_profit == signal.take_profit
    assert loaded.trailing_stop_atr_mult == signal.trailing_stop_atr_mult
    assert loaded.position_size == signal.position_size
    assert loaded.risk_amount == signal.risk_amount
    assert loaded.risk_reward_ratio == signal.risk_reward_ratio
    assert loaded.guards_passed == signal.guards_passed
    assert loaded.ttl == signal.ttl


def test_load_when_empty(store: SignalStore) -> None:
    """Loading without saving should return None."""
    result = store.load_pending()
    assert result is None


def test_save_overwrites(store: SignalStore) -> None:
    """Saving a second signal should overwrite the first."""
    signal_a = _make_signal(date=datetime.date(2026, 3, 10))
    signal_b = _make_signal(date=datetime.date(2026, 3, 11))
    store.save_pending(signal_a)
    store.save_pending(signal_b)

    loaded = store.load_pending()

    assert loaded is not None
    assert loaded.date == datetime.date(2026, 3, 11)


def test_clear_then_load(store: SignalStore) -> None:
    """Saving then clearing should cause load to return None."""
    store.save_pending(_make_signal())
    store.clear_pending()

    result = store.load_pending()
    assert result is None


def test_clear_when_empty(store: SignalStore) -> None:
    """Clearing without having saved should not raise an error."""
    store.clear_pending()  # must not raise
