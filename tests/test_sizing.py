"""Tests for dual-constraint position sizing."""

import pytest

from trading_advisor.portfolio.manager import ThrottleState
from trading_advisor.strategy.sizing import compute_position_size


class TestComputePositionSize:
    """Tests for compute_position_size covering all tiers, throttle states, and edge cases."""

    def test_top_tier_cap_bound(self) -> None:
        """Top tier equity, cap-based constraint wins."""
        result = compute_position_size(
            equity=15000.0,
            cash=15000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(1.09)

    def test_mid_tier_cap_bound(self) -> None:
        """Mid tier equity, cap-based constraint wins."""
        result = compute_position_size(
            equity=10000.0,
            cash=10000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.73)

    def test_low_tier_cap_bound(self) -> None:
        """Low tier equity, cap-based constraint wins."""
        result = compute_position_size(
            equity=4000.0,
            cash=4000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.29)

    def test_atr_bound_wins(self) -> None:
        """ATR-based constraint wins when ATR is very large."""
        result = compute_position_size(
            equity=15000.0,
            cash=15000.0,
            entry_price=2050.6,
            atr=500.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.30)

    def test_throttled_50_halves(self) -> None:
        """THROTTLED_50 halves the computed size."""
        result = compute_position_size(
            equity=15000.0,
            cash=15000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.THROTTLED_50,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.54)

    def test_throttled_max1_no_positions_halves(self) -> None:
        """THROTTLED_MAX1 with no open positions halves the size."""
        result = compute_position_size(
            equity=15000.0,
            cash=15000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.THROTTLED_MAX1,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.54)

    def test_throttled_max1_with_position_blocks(self) -> None:
        """THROTTLED_MAX1 with an existing open position returns 0.0."""
        result = compute_position_size(
            equity=15000.0,
            cash=15000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.THROTTLED_MAX1,
            num_open_positions=1,
        )
        assert result == pytest.approx(0.0)

    def test_halted_blocks(self) -> None:
        """HALTED state always returns 0.0."""
        result = compute_position_size(
            equity=15000.0,
            cash=15000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.HALTED,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.0)

    def test_cash_reserve_reduces_size(self) -> None:
        """Cash reserve constraint reduces size when remaining cash would fall below reserve."""
        result = compute_position_size(
            equity=15000.0,
            cash=5000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.60)

    def test_cash_reserve_too_tight_returns_zero(self) -> None:
        """Returns 0.0 when cash is already below the required reserve."""
        result = compute_position_size(
            equity=15000.0,
            cash=3700.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.0)

    def test_minimum_lot_boundary(self) -> None:
        """Very small equity that results in exactly the minimum lot (0.01)."""
        result = compute_position_size(
            equity=200.0,
            cash=200.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.01)

    def test_below_minimum_lot_returns_zero(self) -> None:
        """Returns 0.0 when computed size is below the minimum lot of 0.01."""
        result = compute_position_size(
            equity=50.0,
            cash=50.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.0)

    def test_tier_boundary_5k(self) -> None:
        """Equity exactly at 5000 uses mid-tier risk_pct (0.015)."""
        result = compute_position_size(
            equity=5000.0,
            cash=5000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.36)

    def test_tier_boundary_15k(self) -> None:
        """Equity exactly at 15000 uses top-tier risk_pct (0.02)."""
        result = compute_position_size(
            equity=15000.0,
            cash=15000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(1.09)

    def test_tier_boundary_just_below_5k(self) -> None:
        """Equity just below 5000 uses low-tier risk_pct (0.01)."""
        result = compute_position_size(
            equity=4999.99,
            cash=4999.99,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.36)

    def test_low_tier_atr_bound_wins(self) -> None:
        """Low tier: ATR-based constraint wins, pinning risk_pct to 0.01."""
        # risk_pct=0.01: atr_based = 4000*0.01/(300.0*2) = 40/600 = 0.06666 → floor 0.06
        # cap_based = 4000*0.15/2050.6 = 0.29260
        # If risk_pct were wrongly 0.015: atr_based = 60/600 = 0.10 → floor 0.10 (different)
        result = compute_position_size(
            equity=4000.0,
            cash=4000.0,
            entry_price=2050.6,
            atr=300.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.06)

    def test_mid_tier_atr_bound_wins(self) -> None:
        """Mid tier: ATR-based constraint wins, pinning risk_pct to 0.015."""
        # risk_pct=0.015: atr_based = 10000*0.015/(300.0*2) = 150/600 = 0.25
        # cap_based = 10000*0.15/2050.6 = 0.73148
        # If risk_pct were wrongly 0.01: atr_based = 100/600 = 0.16666 → floor 0.16 (different)
        # If risk_pct were wrongly 0.02: atr_based = 200/600 = 0.33333 → floor 0.33 (different)
        result = compute_position_size(
            equity=10000.0,
            cash=10000.0,
            entry_price=2050.6,
            atr=300.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.25)

    def test_tier_5k_boundary_atr_bound(self) -> None:
        """Equity just below 5000 uses risk_pct=0.01, not 0.015 at 5000."""
        # risk_pct=0.01: atr_based = 4999.99*0.01/600.0 = 0.08333 → floor 0.08
        # At equity=5000: risk_pct=0.015, atr_based = 5000*0.015/600 = 0.125 → floor 0.12
        # If threshold were wrongly 4000: equity=4999.99 would use 0.015 → 0.12 (different)
        result = compute_position_size(
            equity=4999.99,
            cash=4999.99,
            entry_price=2050.6,
            atr=300.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.08)

    def test_cash_reserve_low_tier(self) -> None:
        """Low tier reserve_pct=0.40 constrains size when cash is tight."""
        # risk_pct=0.01, reserve_pct=0.40
        # atr_based = 4000*0.01/60 = 0.6666; cap_based = 4000*0.15/2050.6 = 0.29260
        # size = min(0.6666, 0.29260) = 0.29260
        # cost = 0.29260 * 2050.6 = 599.99; remaining = 2000 - 600 = 1400
        # required_reserve = 4000*0.40 = 1600; 1400 < 1600 → constrained
        # max_cost = 2000 - 1600 = 400; size = 400/2050.6 = 0.19508 → floor 0.19
        # Wrong reserve_pct 0.30: required=1200, 1400>1200 → no constraint → 0.29
        result = compute_position_size(
            equity=4000.0,
            cash=2000.0,
            entry_price=2050.6,
            atr=30.0,
            throttle_state=ThrottleState.NORMAL,
            num_open_positions=0,
        )
        assert result == pytest.approx(0.19)
