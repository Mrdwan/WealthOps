"""Tests for the run_backtest main loop."""

import datetime
from typing import Any

import pandas as pd
import pytest

from trading_advisor.backtest.engine import (
    BacktestParams,
    ExitReason,
    _to_date,
    run_backtest,
)
from trading_advisor.guards.base import Guard, GuardResult

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_indicators(n: int, **overrides: Any) -> pd.DataFrame:
    """Build n rows of synthetic indicator data with sensible defaults.

    When ``signal`` is overridden but ``composite`` is not, positions with
    signal ``"BUY"`` or ``"STRONG_BUY"`` automatically receive composite=2.0
    so the composite-threshold signal check fires correctly.
    """
    dates = pd.bdate_range("2024-01-01", periods=n, freq="B")
    data: dict[str, Any] = {
        "open": [2000.0] * n,
        "high": [2010.0] * n,
        "low": [1990.0] * n,
        "close": [2000.0] * n,
        "atr_14": [50.0] * n,
        "adx_14": [30.0] * n,
        "ema_8": [2000.0] * n,
        "sma_50": [2000.0] * n,
        "sma_200": [2000.0] * n,
        "rsi_14": [50.0] * n,
        "composite": [0.0] * n,
        "signal": ["NEUTRAL"] * n,
    }
    data.update(overrides)
    # Derive composite from signal when composite was not explicitly provided.
    if "signal" in overrides and "composite" not in overrides:
        composite: list[float] = list(data["composite"])
        for i, sig in enumerate(data["signal"]):
            if sig in ("BUY", "STRONG_BUY"):
                composite[i] = 2.0
        data["composite"] = composite
    return pd.DataFrame(data, index=dates)


def _make_eurusd(n: int) -> pd.DataFrame:
    """Build n rows of synthetic EUR/USD data."""
    dates = pd.bdate_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": [1.10] * n, "sma_200": [1.08] * n}, index=dates)


def _empty_fedfunds() -> "pd.Series[float]":
    """Return an empty FEDFUNDS series."""
    return pd.Series([], dtype=float)


# ------------------------------------------------------------------
# Test: no signals
# ------------------------------------------------------------------


class TestNoSignals:
    """All NEUTRAL signals produce zero trades and flat equity."""

    def test_no_signals(self) -> None:
        """No BUY/STRONG_BUY signals means no trades and equity = starting_capital."""
        n = 10
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)
        capital = 15000.0

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=capital,
            spread_per_side=0.3,
            slippage_per_side=0.1,
        )

        assert len(result.trades) == 0
        assert all(result.equity_curve["equity"] == capital)


# ------------------------------------------------------------------
# Test: signal with no fill
# ------------------------------------------------------------------


class TestSignalNoFill:
    """BUY signal fires but the trap order never fills."""

    def test_signal_no_fill(self) -> None:
        """BUY on day 3, but day 4's high is below buy_stop. Verify 0 trades."""
        n = 10
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"  # day 3 (index 2)

        # buy_stop = high + 0.02*atr = 2010 + 0.02*50 = 2011
        # Day 4 high must stay below 2011 to NOT fill
        highs = [2010.0] * n
        highs[3] = 2005.0  # day 4 high is well below buy_stop

        indicators = _make_indicators(n, signal=signals, high=highs)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        assert len(result.trades) == 0


# ------------------------------------------------------------------
# Test: stop loss exit
# ------------------------------------------------------------------


class TestStopLossExit:
    """BUY signal fills, then SL triggers. Verify negative PnL."""

    def test_sl_exit(self) -> None:
        """BUY signal, fills next day, SL triggered on day after that."""
        # Day 0: NEUTRAL (high=2010)
        # Day 1: NEUTRAL (high=2010)
        # Day 2: BUY signal (high=2010, atr=50)
        #   -> trap: buy_stop = 2010 + 0.02*50 = 2011
        #            limit   = 2011 + 0.05*50 = 2013.5
        # Day 3: fill day -- need high >= 2011 AND low <= 2013.5
        #   -> high=2020, low=1990 -> fills at 2011
        #   -> SL = 2011 - 2*50 = 1911
        #   -> TP = 2011 + 3.0*50 = 2161 (clamp(2+30/30, 2.5, 4.5)=3.0)
        #   -> size = compute_position_size(equity=15000, cash=15000,
        #             entry_price=2011, atr=50, NORMAL, 0)
        #   atr_based = 15000 * 0.02 / (50*2) = 300/100 = 3.0
        #   cap_based = 15000 * 0.15 / 2011 = 2250/2011 = 1.1188...
        #   size = min(3.0, 1.1188) = 1.1188
        #   cash reserve: cost = 1.1188 * 2011 = 2249.89
        #     remaining = 15000 - 2249.89 = 12750.11
        #     required_reserve = 15000 * 0.25 = 3750
        #     12750.11 > 3750 -> ok
        #   floor(1.1188 * 100) / 100 = 1.11
        # Day 4: SL hit -- need low <= 1911
        #   -> high=2000, low=1900
        #   After day 3, position.days_held = 1 (incremented in phase 2)
        #   But on day 3, position was JUST created, so phase 2 runs on day 4
        #   Actually, let's re-read the loop:
        #   - Day 3: Phase 1 fills (creates position), Phase 2 runs on new position
        #     days_held increments to 1, then evaluate_exits
        #     On day 3: high=2020 < 2161 (no TP), low=1990 > 1911 (no SL)
        #     -> no exit. Funding charged for 1 night.
        #   - Day 4: Phase 2: days_held -> 2, evaluate_exits
        #     low=1900 <= 1911 -> SL!
        #     exit price = 1911, size = 1.11
        #     PnL = (1911 - 2011) * 1.11 = -100 * 1.11 = -111.0
        #     funding_share = position.cumulative_funding * (1.11 / 1.11) = all funding
        #     With empty fedfunds, rate=0.0, admin=0.025
        #     notional_for_funding = 2011 * 1.11 = 2232.21
        #     1 night: funding = 2232.21 * 0.025 / 365 = 0.15289...
        #     net_pnl = -111.0 - 0 - 0 - 0.15289... = -111.15289...
        n = 6
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"

        highs = [2010.0] * n
        highs[3] = 2020.0  # fill day
        highs[4] = 2000.0

        lows = [1990.0] * n
        lows[3] = 1990.0
        lows[4] = 1900.0  # SL triggers (1900 <= 1911)

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.STOP_LOSS
        assert trade.entry_price == 2011.0
        assert trade.exit_price == 1911.0
        assert trade.size == 1.11
        assert trade.pnl < 0  # net PnL is negative
        assert trade.spread_cost == 0.0
        assert trade.slippage_cost == 0.0
        # Funding: 1 night held with fedfunds=0, admin=0.025
        # notional = 2011 * 1.11 = 2232.21
        # funding = 2232.21 * 0.025 / 365
        expected_funding = 2011.0 * 1.11 * 0.025 / 365
        assert trade.funding_cost == pytest.approx(expected_funding)
        expected_pnl = (1911.0 - 2011.0) * 1.11 - expected_funding
        assert trade.pnl == pytest.approx(expected_pnl)


# ------------------------------------------------------------------
# Test: time stop exit
# ------------------------------------------------------------------


class TestTimeStopExit:
    """BUY signal fills, price stays flat, time stop at day 10."""

    def test_time_stop(self) -> None:
        """Position held for 10 days hits time stop at close."""
        # Day 0: NEUTRAL
        # Day 1: BUY signal (high=2010, atr=50)
        #   -> trap: buy_stop = 2011, limit = 2013.5
        # Day 2: fill day -- need high >= 2011, low <= 2013.5
        #   -> high=2015, low=1995 -> fills at 2011
        #   -> SL = 1911, TP = 2161
        #   -> size: same as above = 1.11
        # Days 2-11: Phase 2 increments days_held each day
        #   Day 2: days_held = 1
        #   Day 3: days_held = 2
        #   ...
        #   Day 11: days_held = 10 -> TIME_STOP at close
        # Need 12 days total (signal on day 1, fill on day 2, exit on day 11)
        # Keep price flat so no SL/TP triggers:
        #   - low must stay > 1911 (SL)
        #   - high must stay < 2161 (TP)
        n = 14
        signals = ["NEUTRAL"] * n
        signals[1] = "BUY"

        highs = [2010.0] * n
        highs[2] = 2015.0  # fill day

        lows = [1990.0] * n
        lows[2] = 1995.0

        closes = [2000.0] * n

        indicators = _make_indicators(
            n,
            signal=signals,
            high=highs,
            low=lows,
            close=closes,
        )
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.TIME_STOP
        assert trade.entry_price == 2011.0
        assert trade.exit_price == 2000.0  # close on time stop day
        assert trade.days_held == 10

        # Funding: 9 nights (days 2-10 have no exit, funding charged after
        # exit check. Day 11 exits, so no funding on day 11.)
        # Actually: position created on day 2 fill. days_held incremented
        # at start of phase 2 each day position exists.
        # Day 2: days_held=1, no exit -> 1 night funding
        # Day 3: days_held=2, no exit -> 1 night funding
        # ...
        # Day 10: days_held=9, no exit -> 1 night funding
        # Day 11: days_held=10, TIME_STOP -> exit, no funding
        # Total: 9 nights of funding
        notional = 2011.0 * 1.11
        nightly_funding = notional * 0.025 / 365
        expected_funding = nightly_funding * 9
        assert trade.funding_cost == pytest.approx(expected_funding, rel=1e-6)

        expected_pnl = (2000.0 - 2011.0) * 1.11 - expected_funding
        assert trade.pnl == pytest.approx(expected_pnl, rel=1e-6)


# ------------------------------------------------------------------
# Test: TP then trailing stop
# ------------------------------------------------------------------


class TestTpThenTrailing:
    """BUY signal fills, TP hit (50% close), then trailing stop."""

    def test_tp_then_trailing(self) -> None:
        """TP at 50% then trailing stop on remainder. Verify 2 trades."""
        # Setup:
        # Day 0: NEUTRAL
        # Day 1: BUY signal (high=2010, atr=50, adx=30)
        #   -> trap: buy_stop = 2011, limit = 2013.5
        # Day 2: fill -- high=2015, low=1995 -> fills at 2011
        #   SL = 1911, TP = 2161 (mult = clamp(2+30/30, 2.5, 4.5) = 3.0)
        #   size = 1.11, days_held -> 1, no exit -> 1 night funding
        # Day 3: flat, days_held -> 2, no exit -> 1 night funding
        # Day 4: TP hit -- high=2170 >= 2161
        #   days_held -> 3
        #   half = floor(1.11 / 2 * 100) / 100 = floor(55.5) / 100 = 0.55
        #   -> Trade 1: TP exit, size=0.55, price=2161
        #   remaining size = 1.11 - 0.55 = 0.56
        #   After TP exit processing:
        #     tp_50_hit set to True
        #     trailing_stop update: highest_high = max(prev, 2170) = 2170
        #     new_trail = 2170 - 2*50 = 2070
        #     trailing_stop = max(0, 2070) = 2070
        #     Funding charged on remaining: notional = 2011 * 0.56, 1 night
        # Day 5: trailing hit -- low=2060 <= 2070
        #   days_held -> 4
        #   -> Trade 2: TRAILING_STOP exit, size=0.56, price=2070
        n = 8
        signals = ["NEUTRAL"] * n
        signals[1] = "BUY"

        highs = [2010.0] * n
        highs[2] = 2015.0  # fill day
        highs[4] = 2170.0  # TP day (day index 4)
        highs[5] = 2080.0  # after TP

        lows = [1990.0] * n
        lows[2] = 1995.0
        lows[4] = 2000.0  # above SL on TP day
        lows[5] = 2060.0  # trailing stop hit (2060 <= 2070)

        closes = [2000.0] * n
        closes[4] = 2165.0  # TP day close
        closes[5] = 2065.0

        indicators = _make_indicators(
            n,
            signal=signals,
            high=highs,
            low=lows,
            close=closes,
        )
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        assert len(result.trades) == 2

        # Trade 1: TP exit
        t1 = result.trades[0]
        assert t1.exit_reason == ExitReason.TAKE_PROFIT
        assert t1.entry_price == 2011.0
        assert t1.exit_price == 2161.0
        assert t1.size == 0.55

        # Trade 2: trailing stop
        t2 = result.trades[1]
        assert t2.exit_reason == ExitReason.TRAILING_STOP
        assert t2.entry_price == 2011.0
        assert t2.exit_price == 2070.0
        assert t2.size == 0.56

        # PnL checks (zero spread/slippage)
        # Funding accrual for trade 1:
        # Nights with full position (1.11): day 2, day 3 = 2 nights
        # On day 4 (TP day), exit happens first, then funding on remaining
        # cumulative_funding at TP time = 2 nights * (2011*1.11) * 0.025/365
        # funding_share for t1 = cumulative * (0.55 / 1.11)
        notional_full = 2011.0 * 1.11
        nightly_full = notional_full * 0.025 / 365
        cum_at_tp = nightly_full * 2
        funding_t1 = cum_at_tp * (0.55 / 1.11)
        raw_pnl_t1 = (2161.0 - 2011.0) * 0.55
        net_pnl_t1 = raw_pnl_t1 - funding_t1
        assert t1.pnl == pytest.approx(net_pnl_t1, rel=1e-6)
        assert t1.funding_cost == pytest.approx(funding_t1, rel=1e-6)

        # Funding accrual for trade 2:
        # After TP: cumulative_funding reduced by funding_t1
        # remaining cum = cum_at_tp - funding_t1
        # Day 4 (after TP exit): funding charged on remaining (0.56)
        #   notional_remaining = 2011 * 0.56
        #   nightly_remaining = 2011 * 0.56 * 0.025 / 365
        #   cumulative += nightly_remaining
        # Day 5: trailing stop triggers. No more funding.
        # funding_t2 = (cum_at_tp - funding_t1 + nightly_remaining) * (0.56 / 0.56)
        remaining_cum = cum_at_tp - funding_t1
        notional_remaining = 2011.0 * 0.56
        nightly_remaining = notional_remaining * 0.025 / 365
        funding_t2 = remaining_cum + nightly_remaining
        raw_pnl_t2 = (2070.0 - 2011.0) * 0.56
        net_pnl_t2 = raw_pnl_t2 - funding_t2
        assert t2.pnl == pytest.approx(net_pnl_t2, rel=1e-6)
        assert t2.funding_cost == pytest.approx(funding_t2, rel=1e-6)


# ------------------------------------------------------------------
# Test: equity curve shape
# ------------------------------------------------------------------


class TestEquityCurveShape:
    """Verify equity_curve structure and dimensions."""

    def test_equity_curve_shape(self) -> None:
        """Equity curve has correct columns, index type, and length."""
        n = 10
        indicators = _make_indicators(n)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
        )

        ec = result.equity_curve
        assert list(ec.columns) == ["equity", "drawdown_pct", "throttle_state"]
        assert isinstance(ec.index, pd.DatetimeIndex)
        assert len(ec) == n


# ------------------------------------------------------------------
# Test: pending order expires after 1 day
# ------------------------------------------------------------------


class TestPendingOrderExpires:
    """Trap order expires if not filled on the next day."""

    def test_pending_order_expires_then_second_signal_fills(self) -> None:
        """First signal expires unfilled; second signal fills and exits via time stop.

        Day 2 (index 2): BUY signal, high=2010, atr=50
          -> trap: buy_stop=2011, limit=2013.5
        Day 3 (index 3): high too low (2005), order does NOT fill, expires
        Day 5 (index 5): second BUY signal
          -> trap: buy_stop=2011, limit=2013.5
        Day 6 (index 6): high=2015, low=1995 -> fills at 2011
        Days 6-15: position held (days_held 1..10)
        Day 15 (index 15): days_held=10, TIME_STOP at close

        Assert exactly 1 trade from the SECOND signal (proving the first expired).
        """
        n = 18
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"  # first signal -- will expire unfilled
        signals[5] = "BUY"  # second signal -- will fill

        highs = [2010.0] * n
        highs[3] = 2005.0  # day after first signal: high < buy_stop, no fill
        highs[6] = 2015.0  # day after second signal: fills

        lows = [1990.0] * n
        lows[6] = 1995.0  # fill day

        closes = [2000.0] * n

        indicators = _make_indicators(
            n,
            signal=signals,
            high=highs,
            low=lows,
            close=closes,
        )
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        # Exactly 1 trade: from the second signal, not the first
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.TIME_STOP
        assert trade.entry_price == 2011.0
        assert trade.days_held == 10


# ------------------------------------------------------------------
# Test: fill produces zero size (sizing returns 0)
# ------------------------------------------------------------------


class TestFillZeroSize:
    """Signal fills but sizing returns 0 (e.g. too little capital)."""

    def test_fill_zero_size(self) -> None:
        """When compute_position_size returns 0, no position is opened."""
        # capital=100, equity<5000 -> risk_pct=0.01, reserve_pct=0.40
        # atr_based = 100*0.01/(50*2) = 0.01
        # cap_based = 100*0.15/2011 = 0.00745
        # size = 0.00745, floor(0.00745*100)/100 = 0.0 -> returns 0.0
        n = 6
        signals = ["NEUTRAL"] * n
        signals[1] = "BUY"

        highs = [2010.0] * n
        highs[2] = 2015.0

        lows = [1990.0] * n
        lows[2] = 1995.0

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=100.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        assert len(result.trades) == 0
        assert all(result.equity_curve["equity"] == 100.0)


# ------------------------------------------------------------------
# Test: HALTED state blocks new signals
# ------------------------------------------------------------------


class TestHaltedBlocksSignals:
    """When account is HALTED, no new signals are generated."""

    def test_halted_blocks_signals(self) -> None:
        """After big spread cost puts account into HALTED, BUY signals are ignored."""
        # Use exaggerated spread to drain cash on first trade -> HALTED.
        # After SL exit, account is deep in drawdown, subsequent BUY ignored.
        n = 8
        signals = ["NEUTRAL"] * n
        signals[1] = "BUY"  # triggers fill on day 2
        signals[5] = "BUY"  # should be blocked by HALTED

        highs = [2010.0] * n
        highs[2] = 2015.0  # fill day

        lows = [1990.0] * n
        lows[2] = 1995.0
        lows[3] = 1900.0  # SL triggers (1900 <= 1911)

        indicators = _make_indicators(
            n,
            signal=signals,
            high=highs,
            low=lows,
        )
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=5000.0,  # exaggerated to drain cash -> HALTED
            slippage_per_side=0.0,
        )

        # Only 1 trade (the SL exit). The second BUY signal is blocked.
        # Note: both the HALTED check and compute_position_size returning 0
        # block the signal. The HALTED check is an optimisation (skips sizing).
        assert len(result.trades) == 1
        assert result.trades[0].exit_reason == ExitReason.STOP_LOSS

    def test_halted_recovery_allows_new_trade(self) -> None:
        """After HALTED, drawdown dropping below 8% recovers to THROTTLED_50.

        Scenario: trade 1 causes large loss -> HALTED. Equity then rises
        (via favourable close on a subsequent position? No -- we need equity
        to recover above HWM * 0.92 for dd < 8%).

        Simpler approach: use starting_capital such that after the SL loss,
        equity is still above 92% of HWM (since HWM = starting_capital when
        the loss is small relative to capital). Then HALTED doesn't trigger.

        Actually, we need HALTED to trigger and then recover. We use a
        large spread on entry to push equity below 85% of HWM (dd >= 15%),
        then after exit the cash recovers enough for dd < 8%.

        Strategy:
        - starting_capital = 100_000 (large)
        - BUY day 1, fills day 2 with huge spread cost
        - The spread cost pushes equity down temporarily
        - After position exits (SL on day 3), cash is back but minus losses
        - If the net loss puts dd < 8%, HALTED auto-recovers

        Simpler: directly test the state machine by checking throttle_state
        in the equity curve, then checking that a new signal after recovery works.

        Day 1: BUY, fills day 2 with moderate spread. After costs, equity drops
        to ~85% -> HALTED. SL on day 3 closes position. After close, equity
        recovers above 92% of HWM -> auto-recovery to THROTTLED_50.
        Day 6: BUY signal fires (THROTTLED_50 allows signals). Fills day 7.
        Day 7+: time stop eventually. Assert 2 trades.
        """
        # With starting_capital=15000, we need spread to cause dd >= 15%
        # during the position, then recovery after exit.
        # entry_cost = spread_per_side * size (one side on entry)
        # On fill: account.open_position(notional, entry_cost)
        #   cash -= notional + entry_cost
        # Equity during position = cash + unrealized
        # After SL exit: close_position returns proceeds - exit_cost
        #
        # Let's use a different approach: set close prices so that
        # on day 2 (fill day) the close is far below entry, causing
        # dd >= 15%. Then on day 3 the SL triggers. After SL, the loss
        # is smaller (SL is above the close on day 2), so equity partially
        # recovers. Then close rises to recover dd below 8%.
        #
        # entry_price = 2011, SL = 1911, size = 1.11
        # notional = 2011 * 1.11 = 2232.21
        # After open: cash = 15000 - 2232.21 = 12767.79
        # Day 2 close = 1700: unrealized = (1700-2011)*1.11 = -345.21
        # equity = 12767.79 - 345.21 = 12422.58
        # dd = (15000 - 12422.58)/15000 = 17.18% -> HALTED
        # Day 3: SL at 1911: proceeds = 1911 * 1.11 = 2121.21
        # After close: cash = 12767.79 + 2121.21 = 14889.0
        # (minus 1 night funding, small)
        # equity = 14889 (no position), dd = (15000-14889)/15000 = 0.74%
        # dd < 6% -> NORMAL (auto-recover from HALTED goes to THROTTLED_50
        # first, but dd < 6% in same update -> stays THROTTLED_50 on first
        # recovery, then next day's update with dd < 6% -> NORMAL).
        # Wait: the recovery logic is: HALTED + dd < 8% -> THROTTLED_50,
        # then THROTTLED_50 + dd < 6% -> NORMAL. Both in same update? No,
        # update_equity calls _evaluate_throttle once. So:
        # Day 3 update: current=HALTED, dd=0.74% < 8% -> THROTTLED_50
        # Day 4 update: current=THROTTLED_50, dd<6% -> NORMAL
        # Day 6: BUY signal, state is NORMAL -> allowed

        n = 20
        signals = ["NEUTRAL"] * n
        signals[1] = "BUY"
        signals[6] = "BUY"  # after recovery from HALTED

        highs = [2010.0] * n
        highs[2] = 2015.0  # fill day for first trade
        highs[7] = 2015.0  # fill day for second trade

        lows = [1990.0] * n
        lows[2] = 1995.0  # fill day
        lows[3] = 1900.0  # SL triggers
        lows[7] = 1995.0  # fill day for second trade

        closes = [2000.0] * n
        closes[2] = 1700.0  # deep unrealized loss -> HALTED

        indicators = _make_indicators(
            n,
            signal=signals,
            high=highs,
            low=lows,
            close=closes,
        )
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        # Two trades: first exits via SL, second fills after HALTED recovery
        assert len(result.trades) >= 2
        assert result.trades[0].exit_reason == ExitReason.STOP_LOSS

        # Verify HALTED appeared then recovered in equity curve
        states = result.equity_curve["throttle_state"].tolist()
        assert "HALTED" in states
        # After HALTED, should see recovery (THROTTLED_50 or NORMAL)
        halted_idx = states.index("HALTED")
        post_halted = states[halted_idx + 1 :]
        assert any(s != "HALTED" for s in post_halted)


# ------------------------------------------------------------------
# Test: eurusd data missing for signal date
# ------------------------------------------------------------------


class TestEurusdMissing:
    """When eurusd has no row for a signal date, defaults to 0.0."""

    def test_eurusd_missing_date(self) -> None:
        """Signal date not in eurusd index uses 0.0 for guard kwargs.

        BUY on day 2, fills day 3 (no guards, so 0.0 defaults don't block).
        Position exits via time stop on day 12 (10 trading days held).
        Assert exactly 1 trade with correct entry price.
        """
        n = 15
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"

        highs = [2010.0] * n
        highs[3] = 2015.0

        lows = [1990.0] * n
        lows[3] = 1995.0

        closes = [2000.0] * n

        indicators = _make_indicators(
            n,
            signal=signals,
            high=highs,
            low=lows,
            close=closes,
        )

        # Create eurusd with different dates so signal date is NOT in eurusd.index
        eurusd_dates = pd.bdate_range("2024-02-01", periods=n, freq="B")
        eurusd = pd.DataFrame(
            {"close": [1.10] * n, "sma_200": [1.08] * n},
            index=eurusd_dates,
        )

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        # Signal on day 2 creates pending. Day 3 fills. Time stop on day 12.
        assert len(result.trades) == 1
        assert result.trades[0].entry_price == 2011.0
        assert result.trades[0].exit_reason == ExitReason.TIME_STOP


# ------------------------------------------------------------------
# Test: guard blocks signal
# ------------------------------------------------------------------


class _AlwaysFailGuard(Guard):
    """A guard that always fails."""

    @property
    def name(self) -> str:
        """Return guard name."""
        return "always_fail"

    def evaluate(self, **kwargs: object) -> GuardResult:
        """Return a failing result."""
        return GuardResult(
            passed=False,
            guard_name="always_fail",
            reason="blocked",
        )


class TestGuardBlocksSignal:
    """When a guard fails, no pending order is created."""

    def test_guard_blocks_signal(self) -> None:
        """A failing guard prevents trap order creation."""
        n = 6
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"

        indicators = _make_indicators(n, signal=signals)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[_AlwaysFailGuard()],
            guards_enabled={"always_fail": True},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        assert len(result.trades) == 0


# ------------------------------------------------------------------
# Test: signal blocked when position is open
# ------------------------------------------------------------------


class TestSignalBlockedWhenPositionOpen:
    """A BUY signal while a position is already open is ignored."""

    def test_second_signal_ignored_while_position_open(self) -> None:
        """BUY fills, second BUY while position open is ignored, time stop exits.

        Day 1: BUY signal
        Day 2: fills at 2011 (buy_stop)
        Day 4: BUY signal (position still open -> ignored by Phase 4 guard)
        Day 11: days_held=10, TIME_STOP at close
        Assert exactly 1 trade with entry from day 1's signal.
        """
        n = 14
        signals = ["NEUTRAL"] * n
        signals[1] = "BUY"  # first signal -> fills on day 2
        signals[4] = "BUY"  # second signal -> should be blocked (position open)

        highs = [2010.0] * n
        highs[2] = 2015.0  # fill day

        lows = [1990.0] * n
        lows[2] = 1995.0

        closes = [2000.0] * n

        indicators = _make_indicators(
            n,
            signal=signals,
            high=highs,
            low=lows,
            close=closes,
        )
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            spread_per_side=0.0,
            slippage_per_side=0.0,
        )

        # Only 1 trade: the second BUY was blocked because position was open
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.entry_price == 2011.0
        assert trade.exit_reason == ExitReason.TIME_STOP
        assert trade.days_held == 10


# ------------------------------------------------------------------
# Test: empty indicators raises ValueError
# ------------------------------------------------------------------


class TestEmptyIndicators:
    """Empty indicators DataFrame raises ValueError."""

    def test_empty_indicators_raises(self) -> None:
        """Passing an empty indicators DataFrame raises ValueError."""
        empty = pd.DataFrame()
        eurusd = _make_eurusd(5)

        with pytest.raises(ValueError, match="indicators must not be empty"):
            run_backtest(
                indicators=empty,
                eurusd=eurusd,
                guards=[],
                guards_enabled={},
                fedfunds=_empty_fedfunds(),
                starting_capital=15000.0,
            )


# ------------------------------------------------------------------
# Test: _to_date helper
# ------------------------------------------------------------------


class TestToDate:
    """Unit tests for the _to_date private helper."""

    def test_converts_timestamp(self) -> None:
        """pd.Timestamp is converted to datetime.date."""
        ts = pd.Timestamp("2024-03-15")
        result = _to_date(ts)
        assert result == datetime.date(2024, 3, 15)
        assert isinstance(result, datetime.date)

    def test_passthrough_date(self) -> None:
        """datetime.date is returned as-is."""
        d = datetime.date(2024, 3, 15)
        result = _to_date(d)
        assert result == d

    def test_rejects_non_date(self) -> None:
        """Non-date/non-timestamp raises TypeError."""
        with pytest.raises(TypeError, match="Cannot convert"):
            _to_date("2024-03-15")

    def test_rejects_object_with_non_date_date_method(self) -> None:
        """Object with .date() that returns non-date raises TypeError."""

        class _FakeDateable:
            def date(self) -> str:
                return "not-a-date"

        with pytest.raises(TypeError, match="Cannot convert"):
            _to_date(_FakeDateable())


# ------------------------------------------------------------------
# Test: BacktestParams overrides
# ------------------------------------------------------------------


class TestBacktestParams:
    """Tests for BacktestParams overrides."""

    def test_default_params_matches_existing_behavior(self) -> None:
        """run_backtest with explicit default BacktestParams == no params."""
        n = 20
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"
        highs = [2010.0] * n
        highs[3] = 2020.0  # fill day
        lows = [1990.0] * n
        lows[5] = 1900.0  # SL hit

        indicators = _make_indicators(
            n, signal=signals, high=highs, low=lows, composite=[0.0] * 2 + [2.0] + [0.0] * 17
        )
        eurusd = _make_eurusd(n)

        r1 = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
        )
        r2 = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            starting_capital=15000.0,
            params=BacktestParams(),
        )
        assert len(r1.trades) == len(r2.trades)
        assert len(r1.trades) > 0, "Expected trades from test scenario"
        assert len(r2.trades) > 0, "Expected trades from test scenario"
        assert r1.trades[0].pnl == pytest.approx(r2.trades[0].pnl)

    def test_custom_atr_multiplier_changes_sl(self) -> None:
        """Higher ATR mult = wider stop loss = different exit behavior."""
        n = 20
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"
        composites = [0.0] * n
        composites[2] = 2.0
        highs = [2010.0] * n
        highs[3] = 2020.0
        lows = [1990.0] * n
        # SL with atr_mult=2: entry(2011) - 2*50 = 1911
        # SL with atr_mult=3: entry(2011) - 3*50 = 1861
        # Low at 1900 triggers SL for mult=2 but NOT for mult=3
        lows[5] = 1900.0

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows, composite=composites)
        eurusd = _make_eurusd(n)

        r_default = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(atr_multiplier=2.0),
        )
        r_wide = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(atr_multiplier=3.0),
        )
        # Default (2.0) should hit SL, wide (3.0) should NOT hit SL on day 5
        sl_trades = [t for t in r_default.trades if t.exit_reason == ExitReason.STOP_LOSS]
        assert len(sl_trades) > 0, "Default ATR mult should trigger SL"
        # Wide ATR (3.0): SL = 2011 - 3*50 = 1861, low only goes to 1900 -> no SL hit
        assert len(r_wide.trades) > 0, "Expected trades with wide ATR"
        assert all(
            t.exit_reason != ExitReason.STOP_LOSS for t in r_wide.trades
        ), "Wide ATR mult should NOT trigger SL (SL=1861, low=1900)"
        # Should exit via time stop instead
        assert all(
            t.exit_reason == ExitReason.TIME_STOP for t in r_wide.trades
        ), "Wide ATR trade should exit via time stop"

    def test_composite_threshold_controls_signal(self) -> None:
        """Higher threshold = fewer signals."""
        n = 20
        composites = [0.0] * n
        composites[2] = 1.8  # Above 1.5 (default) but below 2.5
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"  # legacy field, ignored when params used
        highs = [2010.0] * n
        highs[3] = 2020.0
        lows = [1990.0] * n
        lows[10] = 1900.0  # eventual SL

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows, composite=composites)
        eurusd = _make_eurusd(n)

        r_low = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(composite_buy_threshold=1.5),
        )
        r_high = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(composite_buy_threshold=2.5),
        )
        # Low threshold (1.5): composite 1.8 > 1.5 -> fires signal -> should have trades
        assert len(r_low.trades) > 0
        # High threshold (2.5): composite 1.8 < 2.5 -> no signal -> no trades
        assert len(r_high.trades) == 0

    def test_fill_price_offset_midpoint(self) -> None:
        """fill_price_offset=0.5 fills at midpoint of buy_stop to limit."""
        n = 20
        composites = [0.0] * n
        composites[2] = 2.0
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"
        highs = [2010.0] * n
        highs[3] = 2020.0
        lows = [1990.0] * n
        lows[10] = 1800.0  # ensure SL hit

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows, composite=composites)
        eurusd = _make_eurusd(n)

        # buy_stop = 2010 + 0.02*50 = 2011
        # limit = 2011 + 0.05*50 = 2013.5
        # midpoint = 2011 + 0.5*(2013.5-2011) = 2012.25

        r_default = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(fill_price_offset=0.0),
        )
        r_mid = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(fill_price_offset=0.5),
        )
        assert len(r_default.trades) > 0, "Expected trades with default fill"
        assert len(r_mid.trades) > 0, "Expected trades with midpoint fill"
        assert r_default.trades[0].entry_price == pytest.approx(2011.0)
        assert r_mid.trades[0].entry_price == pytest.approx(2012.25)

    def test_composite_at_exact_threshold_no_signal(self) -> None:
        """Composite exactly at threshold does not fire (strict >)."""
        n = 20
        composites = [0.0] * n
        composites[2] = 1.5  # Exactly at default threshold
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"
        highs = [2010.0] * n
        highs[3] = 2020.0
        lows = [1990.0] * n

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows, composite=composites)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(composite_buy_threshold=1.5),
        )
        assert len(result.trades) == 0, "Composite exactly at threshold should NOT fire signal"

    def test_composite_just_above_threshold_fires(self) -> None:
        """Composite just above threshold fires signal."""
        n = 20
        composites = [0.0] * n
        composites[2] = 1.5001
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"
        highs = [2010.0] * n
        highs[3] = 2020.0
        lows = [1990.0] * n
        lows[10] = 1800.0  # ensure exit

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows, composite=composites)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
            params=BacktestParams(composite_buy_threshold=1.5),
        )
        assert len(result.trades) > 0, "Composite just above threshold should fire signal"

    def test_nan_composite_no_signal(self) -> None:
        """NaN composite does not fire signal and does not crash."""
        n = 20
        composites: list[float] = [0.0] * n
        composites[2] = float("nan")
        signals = ["NEUTRAL"] * n
        signals[2] = "BUY"
        highs = [2010.0] * n
        highs[3] = 2020.0
        lows = [1990.0] * n

        indicators = _make_indicators(n, signal=signals, high=highs, low=lows, composite=composites)
        eurusd = _make_eurusd(n)

        result = run_backtest(
            indicators=indicators,
            eurusd=eurusd,
            guards=[],
            guards_enabled={},
            fedfunds=_empty_fedfunds(),
        )
        assert len(result.trades) == 0
