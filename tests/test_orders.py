"""Tests for trap order and exit price calculations."""

import pytest

from trading_advisor.strategy.orders import (
    compute_stop_loss,
    compute_take_profit,
    compute_trap_order,
)


class TestComputeTrapOrder:
    """Tests for compute_trap_order."""

    def test_standard_values(self) -> None:
        """Test with standard high and ATR values."""
        buy_stop, limit = compute_trap_order(signal_day_high=2050.0, atr=30.0)
        assert buy_stop == pytest.approx(2050.6)
        assert limit == pytest.approx(2052.1)

    def test_high_atr(self) -> None:
        """Test with high ATR value."""
        buy_stop, limit = compute_trap_order(signal_day_high=2050.0, atr=100.0)
        assert buy_stop == pytest.approx(2052.0)
        assert limit == pytest.approx(2057.0)

    def test_small_atr(self) -> None:
        """Test with small ATR value."""
        buy_stop, limit = compute_trap_order(signal_day_high=2050.0, atr=5.0)
        assert buy_stop == pytest.approx(2050.1)
        assert limit == pytest.approx(2050.35)

    def test_return_type_is_tuple(self) -> None:
        """Verify return type is a tuple of length 2."""
        result = compute_trap_order(signal_day_high=2050.0, atr=30.0)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestComputeStopLoss:
    """Tests for compute_stop_loss."""

    def test_standard_values(self) -> None:
        """Test with standard entry and ATR values."""
        result = compute_stop_loss(entry_price=2050.6, atr=30.0)
        assert result == pytest.approx(1990.6)

    def test_high_atr(self) -> None:
        """Test with high ATR value."""
        result = compute_stop_loss(entry_price=2050.6, atr=100.0)
        assert result == pytest.approx(1850.6)

    def test_small_atr(self) -> None:
        """Test with small ATR value."""
        result = compute_stop_loss(entry_price=2050.1, atr=5.0)
        assert result == pytest.approx(2040.1)


class TestComputeTakeProfit:
    """Tests for compute_take_profit."""

    def test_mid_adx(self) -> None:
        """Test with mid-range ADX (multiplier unclamped)."""
        result = compute_take_profit(entry_price=2050.6, atr=30.0, adx=25.0)
        assert result == pytest.approx(2135.6)

    def test_low_adx_hits_floor(self) -> None:
        """Test with low ADX that hits the floor multiplier of 2.5."""
        result = compute_take_profit(entry_price=2050.6, atr=30.0, adx=10.0)
        assert result == pytest.approx(2125.6)

    def test_zero_adx_hits_floor(self) -> None:
        """Test with zero ADX that hits the floor multiplier of 2.5."""
        result = compute_take_profit(entry_price=2050.6, atr=30.0, adx=0.0)
        assert result == pytest.approx(2125.6)

    def test_high_adx_hits_ceiling(self) -> None:
        """Test with high ADX that hits the ceiling multiplier of 4.5."""
        result = compute_take_profit(entry_price=2050.6, atr=30.0, adx=90.0)
        assert result == pytest.approx(2185.6)

    def test_adx_at_floor_boundary(self) -> None:
        """Test with ADX exactly at the floor boundary (adx=15 gives mult=2.5)."""
        result = compute_take_profit(entry_price=2050.6, atr=30.0, adx=15.0)
        assert result == pytest.approx(2125.6)

    def test_adx_at_ceiling_boundary(self) -> None:
        """Test with ADX exactly at the ceiling boundary (adx=75 gives mult=4.5)."""
        result = compute_take_profit(entry_price=2050.6, atr=30.0, adx=75.0)
        assert result == pytest.approx(2185.6)

    def test_adx_just_above_floor(self) -> None:
        """Test with ADX just above the floor boundary."""
        result = compute_take_profit(entry_price=2050.6, atr=30.0, adx=16.0)
        assert result == pytest.approx(2126.6)
