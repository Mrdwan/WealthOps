"""Tests for backtest exit evaluation logic."""

from datetime import date

from trading_advisor.backtest.engine import (
    ExitEvent,
    ExitReason,
    _ActivePosition,
    evaluate_exits,
)


def _make_position(**overrides: object) -> _ActivePosition:
    """Build an _ActivePosition with sensible defaults."""
    defaults = dict(
        entry_price=2050.0,
        entry_date=date(2024, 1, 2),
        size=0.10,
        original_size=0.10,
        stop_loss=2010.0,
        take_profit=2120.0,
        signal_atr=20.0,
        tp_50_hit=False,
        highest_high=2060.0,
        trailing_stop=0.0,
        days_held=3,
        cumulative_funding=0.0,
    )
    defaults.update(overrides)
    return _ActivePosition(**defaults)  # type: ignore[arg-type]


class TestStopLoss:
    """Tests for stop-loss exit conditions."""

    def test_sl_hit_pre_tp(self) -> None:
        """SL triggers when day_low <= stop_loss (pre-TP)."""
        pos = _make_position(size=0.10, stop_loss=2010.0, tp_50_hit=False)
        result = evaluate_exits(pos, day_high=2060.0, day_low=2005.0, day_close=2020.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2010.0, size=0.10, reason=ExitReason.STOP_LOSS)

    def test_sl_not_hit(self) -> None:
        """No exit when day_low > stop_loss."""
        pos = _make_position(size=0.10, stop_loss=2010.0, tp_50_hit=False)
        result = evaluate_exits(pos, day_high=2060.0, day_low=2011.0, day_close=2050.0)
        assert result == []

    def test_sl_exact_boundary(self) -> None:
        """SL triggers on exact boundary (day_low == stop_loss)."""
        pos = _make_position(size=0.10, stop_loss=2010.0, tp_50_hit=False)
        result = evaluate_exits(pos, day_high=2060.0, day_low=2010.0, day_close=2050.0)
        assert len(result) == 1
        assert result[0].reason == ExitReason.STOP_LOSS

    def test_sl_hit_post_tp(self) -> None:
        """SL triggers post-TP on remaining position."""
        pos = _make_position(size=0.05, stop_loss=2010.0, tp_50_hit=True, trailing_stop=2090.0)
        result = evaluate_exits(pos, day_high=2060.0, day_low=2005.0, day_close=2020.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2010.0, size=0.05, reason=ExitReason.STOP_LOSS)


class TestTakeProfit:
    """Tests for take-profit exit conditions."""

    def test_tp_hit(self) -> None:
        """TP triggers when day_high >= take_profit. Closes 50%."""
        pos = _make_position(size=0.10, take_profit=2120.0, tp_50_hit=False)
        result = evaluate_exits(pos, day_high=2125.0, day_low=2040.0, day_close=2100.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2120.0, size=0.05, reason=ExitReason.TAKE_PROFIT)

    def test_tp_exact_boundary(self) -> None:
        """TP triggers on exact boundary (day_high == take_profit)."""
        pos = _make_position(size=0.10, take_profit=2120.0, tp_50_hit=False)
        result = evaluate_exits(pos, day_high=2120.0, day_low=2040.0, day_close=2100.0)
        assert len(result) == 1
        assert result[0].reason == ExitReason.TAKE_PROFIT

    def test_tp_half_size_rounding(self) -> None:
        """Half-size rounds down to 0.01 lot."""
        # size=0.07, half = floor(0.07/2*100)/100 = floor(3.5)/100 = 0.03
        pos = _make_position(size=0.07)
        result = evaluate_exits(pos, day_high=2125.0, day_low=2040.0, day_close=2100.0)
        assert len(result) == 1
        assert result[0].size == 0.03

    def test_tp_tiny_position_full_close(self) -> None:
        """Position too small to split -- close entire at TP."""
        # size=0.01, half = floor(0.01/2*100)/100 = floor(0.5)/100 = 0.0
        pos = _make_position(size=0.01)
        result = evaluate_exits(pos, day_high=2125.0, day_low=2040.0, day_close=2100.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2120.0, size=0.01, reason=ExitReason.TAKE_PROFIT)

    def test_sl_beats_tp(self) -> None:
        """When SL and TP trigger on same candle, SL wins."""
        pos = _make_position(size=0.10, stop_loss=2010.0, take_profit=2120.0, tp_50_hit=False)
        result = evaluate_exits(pos, day_high=2125.0, day_low=2005.0, day_close=2050.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2010.0, size=0.10, reason=ExitReason.STOP_LOSS)


class TestTrailingStop:
    """Tests for trailing-stop exit conditions."""

    def test_trailing_hit(self) -> None:
        """Trailing stop triggers when day_low <= trailing_stop."""
        pos = _make_position(size=0.05, tp_50_hit=True, trailing_stop=2090.0, days_held=7)
        result = evaluate_exits(pos, day_high=2100.0, day_low=2085.0, day_close=2095.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2090.0, size=0.05, reason=ExitReason.TRAILING_STOP)

    def test_trailing_not_hit(self) -> None:
        """No exit when day_low > trailing_stop."""
        pos = _make_position(size=0.05, tp_50_hit=True, trailing_stop=2090.0, days_held=7)
        result = evaluate_exits(pos, day_high=2100.0, day_low=2091.0, day_close=2095.0)
        assert result == []

    def test_trailing_exact_boundary(self) -> None:
        """Trailing triggers on exact boundary."""
        pos = _make_position(size=0.05, tp_50_hit=True, trailing_stop=2090.0)
        result = evaluate_exits(pos, day_high=2100.0, day_low=2090.0, day_close=2095.0)
        assert len(result) == 1
        assert result[0].reason == ExitReason.TRAILING_STOP

    def test_sl_beats_trailing(self) -> None:
        """SL has higher priority than trailing stop."""
        pos = _make_position(size=0.05, stop_loss=2010.0, tp_50_hit=True, trailing_stop=2090.0)
        result = evaluate_exits(pos, day_high=2100.0, day_low=2005.0, day_close=2050.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2010.0, size=0.05, reason=ExitReason.STOP_LOSS)

    def test_trailing_zero_not_checked(self) -> None:
        """Trailing stop of 0.0 is skipped even when day_low would satisfy <= 0.

        Without the `trailing_stop > 0` guard, day_low=0.0 <= 0.0 would
        spuriously trigger a trailing stop exit.
        """
        result = evaluate_exits(
            _make_position(
                size=0.05,
                tp_50_hit=True,
                trailing_stop=0.0,
                stop_loss=-1.0,
                days_held=3,
            ),
            day_high=2100.0,
            day_low=0.0,
            day_close=2050.0,
        )
        assert result == []


class TestTimeStop:
    """Tests for time-stop exit conditions."""

    def test_time_stop_pre_tp(self) -> None:
        """Time stop triggers at 10 trading days (pre-TP)."""
        pos = _make_position(size=0.10, tp_50_hit=False, days_held=10)
        result = evaluate_exits(pos, day_high=2060.0, day_low=2020.0, day_close=2040.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2040.0, size=0.10, reason=ExitReason.TIME_STOP)

    def test_time_stop_post_tp(self) -> None:
        """Time stop triggers at 10 trading days (post-TP)."""
        pos = _make_position(size=0.05, tp_50_hit=True, trailing_stop=2090.0, days_held=10)
        result = evaluate_exits(pos, day_high=2100.0, day_low=2091.0, day_close=2095.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2095.0, size=0.05, reason=ExitReason.TIME_STOP)

    def test_day_9_no_time_stop(self) -> None:
        """No time stop at day 9."""
        pos = _make_position(size=0.10, tp_50_hit=False, days_held=9)
        result = evaluate_exits(pos, day_high=2060.0, day_low=2020.0, day_close=2040.0)
        assert result == []

    def test_trailing_beats_time_stop(self) -> None:
        """Trailing stop has higher priority than time stop."""
        pos = _make_position(size=0.05, tp_50_hit=True, trailing_stop=2090.0, days_held=10)
        result = evaluate_exits(pos, day_high=2100.0, day_low=2085.0, day_close=2095.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2090.0, size=0.05, reason=ExitReason.TRAILING_STOP)

    def test_sl_beats_time_stop(self) -> None:
        """SL has higher priority than time stop."""
        pos = _make_position(size=0.10, stop_loss=2010.0, tp_50_hit=False, days_held=10)
        result = evaluate_exits(pos, day_high=2060.0, day_low=2005.0, day_close=2040.0)
        assert len(result) == 1
        assert result[0] == ExitEvent(price=2010.0, size=0.10, reason=ExitReason.STOP_LOSS)

    def test_tp_beats_time_stop(self) -> None:
        """TP has higher priority than time stop."""
        pos = _make_position(size=0.10, take_profit=2120.0, tp_50_hit=False, days_held=10)
        result = evaluate_exits(pos, day_high=2125.0, day_low=2020.0, day_close=2040.0)
        assert len(result) == 1
        assert result[0].reason == ExitReason.TAKE_PROFIT


class TestNoExit:
    """Tests for scenarios with no exit."""

    def test_no_exit_normal_day(self) -> None:
        """No exit when no conditions are met."""
        pos = _make_position(
            size=0.10,
            stop_loss=2010.0,
            take_profit=2120.0,
            tp_50_hit=False,
            days_held=3,
        )
        result = evaluate_exits(pos, day_high=2060.0, day_low=2020.0, day_close=2050.0)
        assert result == []
