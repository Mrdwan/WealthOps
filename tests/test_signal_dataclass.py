"""Tests for the TradeSignal frozen dataclass."""

import datetime

import pytest

from trading_advisor.strategy.signal import TradeSignal


def _valid_kwargs() -> dict[str, object]:
    """Return a dict of all valid TradeSignal constructor kwargs."""
    return {
        "date": datetime.date(2024, 6, 15),
        "asset": "XAU/USD",
        "direction": "LONG",
        "composite_score": 1.85,
        "signal_strength": "BUY",
        "trap_order_stop": 2050.6,
        "trap_order_limit": 2052.1,
        "stop_loss": 1990.6,
        "take_profit": 2135.6,
        "trailing_stop_atr_mult": 2.0,
        "position_size": 1.09,
        "risk_amount": 65.4,
        "risk_reward_ratio": 1.4166666666666667,
        "guards_passed": ("MacroGate", "TrendGate", "EventGuard", "PullbackZone", "DrawdownGate"),
        "ttl": 1,
    }


class TestTradeSignal:
    """Tests for the TradeSignal frozen dataclass."""

    def test_construction_valid(self) -> None:
        """Create a valid TradeSignal and assert all fields equal the values passed in."""
        signal = TradeSignal(
            date=datetime.date(2024, 6, 15),
            asset="XAU/USD",
            direction="LONG",
            composite_score=1.85,
            signal_strength="BUY",
            trap_order_stop=2050.6,
            trap_order_limit=2052.1,
            stop_loss=1990.6,
            take_profit=2135.6,
            trailing_stop_atr_mult=2.0,
            position_size=1.09,
            risk_amount=65.4,
            risk_reward_ratio=1.4166666666666667,
            guards_passed=("MacroGate", "TrendGate", "EventGuard", "PullbackZone", "DrawdownGate"),
            ttl=1,
        )
        assert signal.date == datetime.date(2024, 6, 15)
        assert signal.asset == "XAU/USD"
        assert signal.direction == "LONG"
        assert signal.composite_score == 1.85
        assert signal.signal_strength == "BUY"
        assert signal.trap_order_stop == 2050.6
        assert signal.trap_order_limit == 2052.1
        assert signal.stop_loss == 1990.6
        assert signal.take_profit == 2135.6
        assert signal.trailing_stop_atr_mult == 2.0
        assert signal.position_size == 1.09
        assert signal.risk_amount == 65.4
        assert signal.risk_reward_ratio == 1.4166666666666667
        assert signal.guards_passed == (
            "MacroGate",
            "TrendGate",
            "EventGuard",
            "PullbackZone",
            "DrawdownGate",
        )
        assert signal.ttl == 1

    def test_frozen(self) -> None:
        """Assert that mutating a field raises AttributeError (frozen dataclass)."""
        signal = TradeSignal(**_valid_kwargs())  # type: ignore[arg-type]
        with pytest.raises(AttributeError):
            signal.asset = "X"  # type: ignore[misc]

    def test_guards_passed_is_tuple(self) -> None:
        """Assert that guards_passed is a tuple."""
        signal = TradeSignal(**_valid_kwargs())  # type: ignore[arg-type]
        assert isinstance(signal.guards_passed, tuple)

    def test_invalid_position_size_zero(self) -> None:
        """position_size=0.0 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["position_size"] = 0.0
        with pytest.raises(ValueError, match="position_size must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_position_size_negative(self) -> None:
        """position_size=-1.0 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["position_size"] = -1.0
        with pytest.raises(ValueError, match="position_size must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_stop_loss_above_entry(self) -> None:
        """stop_loss above trap_order_stop must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["stop_loss"] = 2060.0
        kwargs["trap_order_stop"] = 2050.6
        with pytest.raises(ValueError, match="stop_loss must be below"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_take_profit_below_entry(self) -> None:
        """take_profit below trap_order_stop must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["take_profit"] = 2040.0
        kwargs["trap_order_stop"] = 2050.6
        with pytest.raises(ValueError, match="trap_order_stop must be below"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_ttl_zero(self) -> None:
        """ttl=0 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["ttl"] = 0
        with pytest.raises(ValueError, match="ttl must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_risk_amount_zero(self) -> None:
        """risk_amount=0.0 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["risk_amount"] = 0.0
        with pytest.raises(ValueError, match="risk_amount must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_risk_reward_negative(self) -> None:
        """risk_reward_ratio=-0.5 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["risk_reward_ratio"] = -0.5
        with pytest.raises(ValueError, match="risk_reward_ratio must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_stop_loss_equal_to_entry(self) -> None:
        """stop_loss equal to trap_order_stop must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["stop_loss"] = 2050.6
        with pytest.raises(ValueError, match="stop_loss must be below"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_take_profit_equal_to_entry(self) -> None:
        """take_profit equal to trap_order_stop must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["take_profit"] = 2050.6
        with pytest.raises(ValueError, match="trap_order_stop must be below"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_trap_order_limit_below_stop(self) -> None:
        """trap_order_limit below trap_order_stop must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["trap_order_limit"] = 2050.0
        with pytest.raises(ValueError, match="trap_order_limit must be above"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_trap_order_limit_equal_to_stop(self) -> None:
        """trap_order_limit equal to trap_order_stop must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["trap_order_limit"] = 2050.6
        with pytest.raises(ValueError, match="trap_order_limit must be above"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_risk_reward_zero(self) -> None:
        """risk_reward_ratio=0.0 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["risk_reward_ratio"] = 0.0
        with pytest.raises(ValueError, match="risk_reward_ratio must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_risk_amount_negative(self) -> None:
        """risk_amount=-10.0 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["risk_amount"] = -10.0
        with pytest.raises(ValueError, match="risk_amount must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]

    def test_invalid_ttl_negative(self) -> None:
        """ttl=-1 must raise ValueError."""
        kwargs = _valid_kwargs()
        kwargs["ttl"] = -1
        with pytest.raises(ValueError, match="ttl must be positive"):
            TradeSignal(**kwargs)  # type: ignore[arg-type]
