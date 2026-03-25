"""Tests for backtest engine foundation types and fill logic."""

from dataclasses import FrozenInstanceError
from datetime import date

import pandas as pd
import pytest

from trading_advisor.backtest.engine import (
    BacktestAccount,
    BacktestResult,
    ExitReason,
    Trade,
    check_fill,
)
from trading_advisor.portfolio.manager import ThrottleState


class TestExitReason:
    """Tests for ExitReason enum."""

    def test_values(self) -> None:
        """All four exit reasons exist with correct string values."""
        assert ExitReason.STOP_LOSS.value == "STOP_LOSS"
        assert ExitReason.TAKE_PROFIT.value == "TAKE_PROFIT"
        assert ExitReason.TRAILING_STOP.value == "TRAILING_STOP"
        assert ExitReason.TIME_STOP.value == "TIME_STOP"


class TestTrade:
    """Tests for Trade frozen dataclass."""

    def _make_trade(self) -> Trade:
        return Trade(
            entry_date=date(2024, 1, 2),
            exit_date=date(2024, 1, 5),
            entry_price=2050.0,
            exit_price=2010.0,
            size=0.05,
            direction="LONG",
            pnl=-2.04,
            exit_reason=ExitReason.STOP_LOSS,
            days_held=3,
            spread_cost=0.03,
            slippage_cost=0.01,
            funding_cost=0.0,
        )

    def test_construction(self) -> None:
        """Trade can be constructed with all fields."""
        t = self._make_trade()
        assert t.entry_price == 2050.0
        assert t.exit_reason == ExitReason.STOP_LOSS
        assert t.pnl == -2.04

    def test_frozen(self) -> None:
        """Trade is immutable."""
        t = self._make_trade()
        with pytest.raises(FrozenInstanceError):
            t.pnl = 0.0  # type: ignore[misc]


class TestBacktestResult:
    """Tests for BacktestResult frozen dataclass."""

    def test_construction(self) -> None:
        """BacktestResult holds equity curve and trades."""
        equity_curve = pd.DataFrame(
            {"equity": [], "drawdown_pct": [], "throttle_state": []},
            index=pd.DatetimeIndex([]),
        )
        result = BacktestResult(
            equity_curve=equity_curve,
            trades=(),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            starting_capital=15000.0,
        )
        assert result.starting_capital == 15000.0
        assert result.trades == ()
        assert list(result.equity_curve.columns) == ["equity", "drawdown_pct", "throttle_state"]


class TestBacktestAccount:
    """Tests for BacktestAccount mutable class."""

    def test_initial_state(self) -> None:
        """Account starts with correct initial values."""
        a = BacktestAccount(15000.0)
        assert a.cash == 15000.0
        assert a.high_water_mark == 15000.0
        assert a.drawdown == 0.0
        assert a.throttle_state == ThrottleState.NORMAL

    def test_open_position(self) -> None:
        """Cash decreases by notional + entry cost."""
        a = BacktestAccount(15000.0)
        a.open_position(notional=102.5, entry_cost=0.02)
        assert a.cash == pytest.approx(14897.48)

    def test_close_position(self) -> None:
        """Cash increases by proceeds minus exit cost."""
        a = BacktestAccount(15000.0)
        a.open_position(notional=102.5, entry_cost=0.02)
        a.close_position(proceeds=103.0, exit_cost=0.02)
        assert a.cash == pytest.approx(15000.46)

    def test_charge_funding(self) -> None:
        """Funding deducted from cash."""
        a = BacktestAccount(15000.0)
        a.open_position(notional=102.5, entry_cost=0.02)
        a.charge_funding(0.02)
        assert a.cash == pytest.approx(14897.46)

    def test_update_equity_hwm_increases(self) -> None:
        """HWM increases when equity rises."""
        a = BacktestAccount(15000.0)
        a.update_equity(16000.0)
        assert a.high_water_mark == 16000.0
        assert a.drawdown == 0.0

    def test_update_equity_drawdown(self) -> None:
        """Drawdown calculated correctly when equity drops."""
        a = BacktestAccount(15000.0)
        a.update_equity(14000.0)
        # DD = (15000 - 14000) / 15000 = 0.06667
        assert a.drawdown == pytest.approx(1000.0 / 15000.0)
        assert a.throttle_state == ThrottleState.NORMAL  # 6.67% < 8%

    def test_throttle_escalation_to_throttled_50(self) -> None:
        """DD >= 8% triggers THROTTLED_50."""
        a = BacktestAccount(15000.0)
        a.update_equity(13800.0)  # DD = 1200/15000 = 0.08
        assert a.throttle_state == ThrottleState.THROTTLED_50

    def test_throttle_escalation_to_max1(self) -> None:
        """DD >= 12% triggers THROTTLED_MAX1."""
        a = BacktestAccount(15000.0)
        a.update_equity(13200.0)  # DD = 1800/15000 = 0.12
        assert a.throttle_state == ThrottleState.THROTTLED_MAX1

    def test_throttle_escalation_to_halted(self) -> None:
        """DD >= 15% triggers HALTED."""
        a = BacktestAccount(15000.0)
        a.update_equity(12750.0)  # DD = 2250/15000 = 0.15
        assert a.throttle_state == ThrottleState.HALTED

    def test_auto_recover_halted_to_throttled_50(self) -> None:
        """In backtest mode (auto_recover=True), HALTED recovers to THROTTLED_50 when DD < 8%."""
        a = BacktestAccount(15000.0)
        a.update_equity(12750.0)  # HALTED (DD=15%)
        assert a.throttle_state == ThrottleState.HALTED
        a.update_equity(13900.0)  # DD = 1100/15000 = 7.33% < 8%
        assert a.throttle_state == ThrottleState.THROTTLED_50  # auto-recover

    def test_recovery_throttled_50_to_normal(self) -> None:
        """THROTTLED_50 recovers to NORMAL only when DD < 6%."""
        a = BacktestAccount(15000.0)
        a.update_equity(13800.0)  # THROTTLED_50 (DD=8%)
        assert a.throttle_state == ThrottleState.THROTTLED_50
        a.update_equity(14200.0)  # DD = 800/15000 = 5.33% < 6%
        assert a.throttle_state == ThrottleState.NORMAL

    def test_recovery_throttled_50_stays_at_7pct(self) -> None:
        """THROTTLED_50 stays if DD between 6% and 8% (hysteresis)."""
        a = BacktestAccount(15000.0)
        a.update_equity(13800.0)  # THROTTLED_50 (DD=8%)
        a.update_equity(14000.0)  # DD = 1000/15000 = 6.67% — between 6% and 8%
        assert a.throttle_state == ThrottleState.THROTTLED_50

    def test_recovery_max1_to_throttled_50(self) -> None:
        """THROTTLED_MAX1 recovers to THROTTLED_50 when DD < 8%."""
        a = BacktestAccount(15000.0)
        a.update_equity(13200.0)  # THROTTLED_MAX1 (DD=12%)
        a.update_equity(13900.0)  # DD = 7.33% < 8%
        assert a.throttle_state == ThrottleState.THROTTLED_50

    def test_drawdown_property_hwm_zero(self) -> None:
        """Drawdown is 0.0 when HWM is 0."""
        a = BacktestAccount(0.0)
        assert a.drawdown == 0.0

    def test_halted_stays_halted_at_dd_max1_range(self) -> None:
        """HALTED stays HALTED when DD is between 12% and 15% (no auto-recovery until < 8%)."""
        a = BacktestAccount(15000.0)
        a.update_equity(12750.0)  # HALTED (DD=15%)
        assert a.throttle_state == ThrottleState.HALTED
        a.update_equity(13050.0)  # DD = 1950/15000 = 13% — still > MAX1, current=HALTED
        assert a.throttle_state == ThrottleState.HALTED

    def test_throttled_max1_stays_at_max1_when_dd_in_throttle_range(self) -> None:
        """THROTTLED_MAX1 stays when DD is between 8% and 12% (no downgrade until < 8%)."""
        a = BacktestAccount(15000.0)
        a.update_equity(13200.0)  # THROTTLED_MAX1 (DD=12%)
        assert a.throttle_state == ThrottleState.THROTTLED_MAX1
        a.update_equity(13650.0)  # DD = 1350/15000 = 9% — between 8% and 12%
        assert a.throttle_state == ThrottleState.THROTTLED_MAX1

    def test_halted_stays_halted_when_dd_in_throttle_range(self) -> None:
        """HALTED stays HALTED when DD is between 8% and 12% (requires full recovery to < 8%)."""
        a = BacktestAccount(15000.0)
        a.update_equity(12750.0)  # HALTED (DD=15%)
        assert a.throttle_state == ThrottleState.HALTED
        a.update_equity(13650.0)  # DD = 1350/15000 = 9% — between 8% and 12%
        assert a.throttle_state == ThrottleState.HALTED


class TestCheckFill:
    """Tests for check_fill function."""

    def test_clean_fill(self) -> None:
        """Order fills when high reaches buy_stop and low is below limit."""
        assert check_fill(2050.0, 2051.5, day_high=2055.0, day_low=2045.0) is True

    def test_high_below_buy_stop(self) -> None:
        """Order does not fill when high never reaches buy_stop."""
        assert check_fill(2050.0, 2051.5, day_high=2049.0, day_low=2040.0) is False

    def test_gap_through(self) -> None:
        """Low above limit means price gapped through — no fill."""
        assert check_fill(2050.0, 2051.5, day_high=2055.0, day_low=2052.0) is False

    def test_exact_boundary(self) -> None:
        """Order fills at exact boundary values."""
        assert check_fill(2050.0, 2051.5, day_high=2050.0, day_low=2051.5) is True

    def test_high_equals_buy_stop(self) -> None:
        """Order fills when high exactly equals buy_stop."""
        assert check_fill(2050.0, 2051.5, day_high=2050.0, day_low=2045.0) is True

    def test_low_equals_limit(self) -> None:
        """Order fills when low exactly equals limit."""
        assert check_fill(2050.0, 2051.5, day_high=2055.0, day_low=2051.5) is True
