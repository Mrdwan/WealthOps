"""Tests for SwingSniper signal generation pipeline."""

import datetime

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from trading_advisor.guards.base import Guard, GuardResult
from trading_advisor.portfolio.manager import PortfolioManager, PortfolioState, ThrottleState
from trading_advisor.strategy.signal import TradeSignal
from trading_advisor.strategy.swing_sniper import SwingSniper


class _StubGuard(Guard):
    """Stub guard that always passes or fails based on constructor arg."""

    def __init__(self, name: str, passes: bool = True) -> None:
        self._name = name
        self._passes = passes

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, **kwargs: object) -> GuardResult:
        return GuardResult(
            passed=self._passes,
            guard_name=self._name,
            reason="stub" if self._passes else "blocked",
        )


def _make_indicators(
    date: datetime.date,
    signal: str = "BUY",
    composite: float = 1.85,
    high: float = 2050.0,
    close: float = 2045.0,
    atr_14: float = 30.0,
    adx_14: float = 25.0,
    ema_8: float = 2044.0,
) -> pd.DataFrame:
    """Build a single-row indicators DataFrame for testing."""
    ts = pd.Timestamp(date)
    return pd.DataFrame(
        {
            "signal": [signal],
            "composite": [composite],
            "high": [high],
            "close": [close],
            "atr_14": [atr_14],
            "adx_14": [adx_14],
            "ema_8": [ema_8],
        },
        index=pd.DatetimeIndex([ts]),
    )


def _make_eurusd(
    date: datetime.date,
    close: float = 1.08,
    sma_200: float = 1.05,
) -> pd.DataFrame:
    """Build a single-row EUR/USD DataFrame for testing."""
    ts = pd.Timestamp(date)
    return pd.DataFrame(
        {"close": [close], "sma_200": [sma_200]},
        index=pd.DatetimeIndex([ts]),
    )


def _mock_portfolio(
    mocker: MockerFixture,
    cash: float = 15000.0,
    positions: tuple[object, ...] = (),
    throttle: ThrottleState = ThrottleState.NORMAL,
    drawdown: float = 0.0,
) -> PortfolioManager:
    """Build a mocked PortfolioManager with the given state."""
    pm: PortfolioManager = mocker.MagicMock(spec=PortfolioManager)
    pm.state = PortfolioState(  # type: ignore[misc]
        cash=cash,
        positions=positions,  # type: ignore[arg-type]
        high_water_mark=cash,
        throttle_state=throttle,
    )
    pm.get_drawdown.return_value = drawdown  # type: ignore[attr-defined]
    pm.get_throttle_state.return_value = throttle  # type: ignore[attr-defined]
    return pm


class TestSwingSniper:
    """Tests for SwingSniper.generate_signals."""

    def test_valid_buy_signal(self, mocker: MockerFixture) -> None:
        """BUY signal with all guards passing produces a correct TradeSignal."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date)
        eurusd = _make_eurusd(date)
        pm = _mock_portfolio(mocker)

        guards = [_StubGuard("MacroGate"), _StubGuard("TrendGate")]
        enabled: dict[str, bool] = {"MacroGate": True, "TrendGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert len(result) == 1
        sig = result[0]
        assert isinstance(sig, TradeSignal)

        # Pre-computed values:
        # buy_stop = 2050.0 + 0.02*30.0 = 2050.6
        # limit = 2050.6 + 0.05*30.0 = 2052.1
        assert sig.trap_order_stop == pytest.approx(2050.6)
        assert sig.trap_order_limit == pytest.approx(2052.1)

        # SL = 2050.6 - 2*30.0 = 1990.6
        assert sig.stop_loss == pytest.approx(1990.6)

        # TP mult = max(2.5, min(4.5, 2 + 25/30)) = max(2.5, min(4.5, 2.8333...)) = 2.8333...
        # TP = 2050.6 + 2.8333...*30.0 = 2050.6 + 85.0 = 2135.6
        assert sig.take_profit == pytest.approx(2135.6, rel=1e-4)

        # size: cap_based = 15000*0.15/2050.6 = 1.09724... -> floor = 1.09
        assert sig.position_size == pytest.approx(1.09)

        # risk_per_unit = 2050.6 - 1990.6 = 60.0
        # risk_amount = 1.09 * 60.0 = 65.4
        assert sig.risk_amount == pytest.approx(65.4)

        # reward_per_unit = 2135.6 - 2050.6 = 85.0
        # risk_reward = 85.0 / 60.0 = 1.4166...
        assert sig.risk_reward_ratio == pytest.approx(85.0 / 60.0, rel=1e-4)

        assert sig.date == date
        assert sig.asset == "XAU/USD"
        assert sig.direction == "LONG"
        assert sig.composite_score == pytest.approx(1.85)
        assert sig.signal_strength == "BUY"
        assert sig.trailing_stop_atr_mult == 2.0
        assert sig.ttl == 1
        assert sig.guards_passed == ("MacroGate", "TrendGate")

    def test_strong_buy_proceeds(self, mocker: MockerFixture) -> None:
        """STRONG_BUY signal also produces a TradeSignal."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date, signal="STRONG_BUY", composite=2.5)
        eurusd = _make_eurusd(date)
        pm = _mock_portfolio(mocker)

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert len(result) == 1
        sig = result[0]
        assert isinstance(sig, TradeSignal)
        assert sig.signal_strength == "STRONG_BUY"

    def test_neutral_signal_no_output(self, mocker: MockerFixture) -> None:
        """NEUTRAL signal produces no output."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date, signal="NEUTRAL", composite=0.5)
        eurusd = _make_eurusd(date)
        pm = _mock_portfolio(mocker)

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert result == []

    def test_sell_signal_no_output(self, mocker: MockerFixture) -> None:
        """SELL signal produces no output."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date, signal="SELL", composite=-1.8)
        eurusd = _make_eurusd(date)
        pm = _mock_portfolio(mocker)

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert result == []

    def test_guard_failure_no_output(self, mocker: MockerFixture) -> None:
        """A failing guard blocks signal generation."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date)
        eurusd = _make_eurusd(date)
        pm = _mock_portfolio(mocker)

        guards = [_StubGuard("MacroGate"), _StubGuard("TrendGate", passes=False)]
        enabled: dict[str, bool] = {"MacroGate": True, "TrendGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert result == []

    def test_partial_position_blocks(self, mocker: MockerFixture) -> None:
        """An open position blocks signal generation (partial position rule)."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date)
        eurusd = _make_eurusd(date)

        fake_pos = mocker.MagicMock()
        pm = _mock_portfolio(mocker, positions=(fake_pos,))

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert result == []

    def test_date_not_in_index_no_output(self, mocker: MockerFixture) -> None:
        """Date not in indicators index produces no output."""
        date_in_index = datetime.date(2024, 6, 15)
        eval_date = datetime.date(2024, 6, 16)
        indicators = _make_indicators(date_in_index)
        eurusd = _make_eurusd(date_in_index)
        pm = _mock_portfolio(mocker)

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(
            indicators=indicators, eurusd=eurusd, evaluation_date=eval_date
        )

        assert result == []

    def test_zero_size_no_output(self, mocker: MockerFixture) -> None:
        """Too little cash for minimum lot produces no output."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date)
        eurusd = _make_eurusd(date)
        pm = _mock_portfolio(mocker, cash=50.0)

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert result == []

    def test_halted_no_output(self, mocker: MockerFixture) -> None:
        """HALTED throttle state blocks signal generation."""
        date = datetime.date(2024, 6, 15)
        indicators = _make_indicators(date)
        eurusd = _make_eurusd(date)
        pm = _mock_portfolio(mocker, throttle=ThrottleState.HALTED)

        guards = [_StubGuard("MacroGate")]
        enabled: dict[str, bool] = {"MacroGate": True}

        sniper = SwingSniper(portfolio=pm, guards=guards, guards_enabled=enabled)
        result = sniper.generate_signals(indicators=indicators, eurusd=eurusd, evaluation_date=date)

        assert result == []
