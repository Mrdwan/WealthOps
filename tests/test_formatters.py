"""Tests for notification formatters: signal card, daily briefing, heartbeat."""

import datetime

from trading_advisor.notifications.formatters import (
    BriefingData,
    format_daily_briefing,
    format_heartbeat,
    format_signal_card,
)
from trading_advisor.portfolio.manager import (
    PortfolioState,
    Position,
    ThrottleState,
)
from trading_advisor.strategy.signal import TradeSignal

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_strong_buy_signal() -> TradeSignal:
    return TradeSignal(
        date=datetime.date(2026, 3, 10),
        asset="XAU/USD",
        direction="LONG",
        composite_score=2.15,
        signal_strength="STRONG_BUY",
        trap_order_stop=2352.40,
        trap_order_limit=2353.85,
        stop_loss=2310.00,
        take_profit=2410.00,
        trailing_stop_atr_mult=2.0,
        position_size=0.05,
        risk_amount=212.00,
        risk_reward_ratio=2.72,
        guards_passed=("MacroGate", "TrendGate", "EventGuard", "PullbackZone", "DrawdownGate"),
        ttl=1,
    )


def _make_buy_signal() -> TradeSignal:
    return TradeSignal(
        date=datetime.date(2026, 3, 10),
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
        guards_passed=("MacroGate", "TrendGate", "EventGuard", "PullbackZone", "DrawdownGate"),
        ttl=1,
    )


def _make_multi_day_signal() -> TradeSignal:
    return TradeSignal(
        date=datetime.date(2026, 3, 10),
        asset="XAU/USD",
        direction="LONG",
        composite_score=1.55,
        signal_strength="BUY",
        trap_order_stop=2352.40,
        trap_order_limit=2353.85,
        stop_loss=2310.00,
        take_profit=2410.00,
        trailing_stop_atr_mult=2.0,
        position_size=0.05,
        risk_amount=212.00,
        risk_reward_ratio=2.72,
        guards_passed=("MacroGate",),
        ttl=2,
    )


# ------------------------------------------------------------------
# format_signal_card tests
# ------------------------------------------------------------------


class TestFormatSignalCard:
    def test_strong_buy_signal(self) -> None:
        """STRONG_BUY signal card contains all expected fields."""
        signal = _make_strong_buy_signal()
        result = format_signal_card(signal)

        assert "STRONG BUY" in result
        assert "XAU/USD" in result
        assert "+2.15σ" in result
        assert "2026-03-10" in result
        assert "2352.40" in result
        assert "2353.85" in result
        assert "2310.00" in result
        assert "2410.00" in result
        assert "0.05" in result
        assert "212.00" in result
        assert "2.72" in result
        assert "MacroGate" in result
        assert "DrawdownGate" in result
        assert "1 trading day" in result

    def test_buy_signal(self) -> None:
        """BUY signal card shows 'BUY Signal' but not 'STRONG BUY'."""
        signal = _make_buy_signal()
        result = format_signal_card(signal)

        assert "BUY Signal" in result
        assert "STRONG BUY" not in result
        assert "+1.65σ" in result

    def test_ttl_plural(self) -> None:
        """TTL > 1 shows 'trading days' (plural)."""
        signal = _make_multi_day_signal()
        result = format_signal_card(signal)

        assert "2 trading days" in result

    def test_signal_card_structure(self) -> None:
        """Signal card contains all section headers."""
        signal = _make_strong_buy_signal()
        result = format_signal_card(signal)

        assert "Entry" in result
        assert "Risk Management" in result
        assert "Position" in result
        assert "Guards" in result
        assert "Valid" in result


# ------------------------------------------------------------------
# format_daily_briefing tests
# ------------------------------------------------------------------


class TestFormatDailyBriefing:
    def test_with_position(self) -> None:
        """Briefing with open position shows all expected fields."""
        data = BriefingData(
            date=datetime.date(2026, 3, 10),
            portfolio_state=PortfolioState(
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
            ),
            equity=15005.0,
            starting_capital=15000.0,
            current_prices={"XAU/USD": 2050.0},
            composite_score=1.20,
            signal_class="NEUTRAL",
            pending_signal=None,
        )
        result = format_daily_briefing(data)

        assert "15005.00" in result
        assert "14800.00" in result
        # Position unrealized P&L of +5.00
        assert "P&L: +€5.00" in result
        # Days held = 3 (2026-03-10 - 2026-03-07)
        assert "Days: 3" in result
        # Drawdown: max(0, (15000 - 15005) / 15000 * 100) = 0.0% (equity exceeds HWM)
        assert "0.0%" in result
        assert "NORMAL" in result
        assert "+1.20σ" in result
        assert "NEUTRAL" in result
        assert "No signal today." in result
        # No "Cash is a position" message when there is an open position
        assert "Cash is a position" not in result

    def test_empty_portfolio(self) -> None:
        """Empty portfolio shows 'None' and 'Cash is a position' message."""
        data = BriefingData(
            date=datetime.date(2026, 3, 10),
            portfolio_state=PortfolioState(
                cash=15000.0,
                positions=(),
                high_water_mark=15000.0,
                throttle_state=ThrottleState.NORMAL,
            ),
            equity=15000.0,
            starting_capital=15000.0,
            current_prices={},
            composite_score=-0.50,
            signal_class="NEUTRAL",
            pending_signal=None,
        )
        result = format_daily_briefing(data)

        assert "None" in result
        assert "Cash is a position" in result
        assert "15000.00" in result
        # Drawdown: 0.0%
        assert "0.0" in result

    def test_throttled_state(self) -> None:
        """Throttled state is shown in the Risk section."""
        data = BriefingData(
            date=datetime.date(2026, 3, 10),
            portfolio_state=PortfolioState(
                cash=15000.0,
                positions=(),
                high_water_mark=15000.0,
                throttle_state=ThrottleState.THROTTLED_50,
            ),
            equity=15000.0,
            starting_capital=15000.0,
            current_prices={},
            composite_score=-0.50,
            signal_class="NEUTRAL",
            pending_signal=None,
        )
        result = format_daily_briefing(data)

        assert "THROTTLED_50" in result

    def test_with_pending_signal(self) -> None:
        """Pending signal shows 'Pending signal' and not 'Cash is a position'."""
        pending = _make_strong_buy_signal()
        data = BriefingData(
            date=datetime.date(2026, 3, 10),
            portfolio_state=PortfolioState(
                cash=15000.0,
                positions=(),
                high_water_mark=15000.0,
                throttle_state=ThrottleState.NORMAL,
            ),
            equity=15000.0,
            starting_capital=15000.0,
            current_prices={},
            composite_score=2.15,
            signal_class="STRONG_BUY",
            pending_signal=pending,
        )
        result = format_daily_briefing(data)

        assert "Pending signal" in result
        assert "Cash is a position" not in result

    def test_negative_pnl(self) -> None:
        """Negative P&L is formatted with a minus sign."""
        data = BriefingData(
            date=datetime.date(2026, 3, 10),
            portfolio_state=PortfolioState(
                cash=14000.0,
                positions=(),
                high_water_mark=15000.0,
                throttle_state=ThrottleState.NORMAL,
            ),
            equity=14000.0,
            starting_capital=15000.0,
            current_prices={},
            composite_score=0.0,
            signal_class="NEUTRAL",
            pending_signal=None,
        )
        result = format_daily_briefing(data)

        # P&L is -1000, P&L% is -6.7%
        assert "-€1000.00" in result
        assert "-6.7%" in result

    def test_zero_hwm_drawdown(self) -> None:
        """Zero HWM results in 0.0% drawdown (no division by zero)."""
        data = BriefingData(
            date=datetime.date(2026, 3, 10),
            portfolio_state=PortfolioState(
                cash=15000.0,
                positions=(),
                high_water_mark=0.0,
                throttle_state=ThrottleState.NORMAL,
            ),
            equity=15000.0,
            starting_capital=15000.0,
            current_prices={},
            composite_score=0.0,
            signal_class="NEUTRAL",
            pending_signal=None,
        )
        result = format_daily_briefing(data)

        assert "0.0%" in result


# ------------------------------------------------------------------
# format_heartbeat tests
# ------------------------------------------------------------------


class TestFormatHeartbeat:
    def test_ingest_heartbeat(self) -> None:
        """Ingest heartbeat is formatted as a single line."""
        result = format_heartbeat(
            command="ingest",
            timestamp=datetime.datetime(2026, 3, 10, 23, 0, tzinfo=datetime.UTC),
            duration_s=0.4,
            composite=1.2,
            signal_class="NEUTRAL",
        )
        assert result == "✓ ingest 2026-03-10 23:00 UTC — 0.4s — XAU composite: 1.2σ NEUTRAL"

    def test_briefing_heartbeat(self) -> None:
        """Briefing heartbeat with negative composite is formatted correctly."""
        result = format_heartbeat(
            command="briefing",
            timestamp=datetime.datetime(2026, 3, 10, 9, 0, tzinfo=datetime.UTC),
            duration_s=1.23,
            composite=-0.5,
            signal_class="NEUTRAL",
        )
        assert result == "✓ briefing 2026-03-10 09:00 UTC — 1.2s — XAU composite: -0.5σ NEUTRAL"
