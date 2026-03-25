# Plan: Backtest Engine

## Goal

Implement the backtest engine (Task 1E) — a day-by-day execution simulator that takes pre-computed indicators, composite scores, EUR/USD data, guards, and FEDFUNDS rates, and produces an equity curve, trade log, and performance metrics. Costs include IG spread (0.3 pts/side), slippage (0.1 pts/side), and overnight funding (~FEDFUNDS + 2.5% annualized). Output is a `BacktestResult` containing equity curve DataFrame, trade list, and a Plotly HTML report.

## Pseudocode (Task 1E.1)

```
run_backtest(indicators, eurusd, guards, guards_enabled, fedfunds,
             starting_capital=15000, spread=0.3, slippage=0.1):

  account = BacktestAccount(starting_capital)
  trades = []
  equity_records = []
  pending = None          # PendingOrder | None
  position = None         # ActivePosition | None

  for date in sorted(indicators.index):
    row = indicators.loc[date]
    H, L, C = row.high, row.low, row.close

    # ── Phase 1: Fill pending trap order ──────────────────────────
    if pending is not None:
      if check_fill(pending.buy_stop, pending.limit, H, L):
        size = compute_position_size(account.equity, account.cash,
                   pending.buy_stop, pending.signal_atr,
                   account.throttle_state, 0)
        if size > 0:
          sl = compute_stop_loss(pending.buy_stop, pending.signal_atr)
          tp = compute_take_profit(pending.buy_stop, pending.signal_atr,
                                   pending.signal_adx)
          account.open_position(size * pending.buy_stop,
                                (spread + slippage) * size)
          position = ActivePosition(
              entry_price=pending.buy_stop, entry_date=date,
              size=size, original_size=size,
              stop_loss=sl, take_profit=tp,
              signal_atr=pending.signal_atr,
              tp_50_hit=False, highest_high=H,
              trailing_stop=0.0, days_held=0,
              cumulative_funding=0.0)
      pending = None   # expires regardless

    # ── Phase 2: Evaluate exits ───────────────────────────────────
    if position is not None:
      position.days_held += 1
      position.highest_high = max(position.highest_high, H)

      exits = evaluate_exits(position, H, L, C)
      for ev in exits:                            # 0, 1, or 2 events
        pnl = (ev.price - position.entry_price) * ev.size
        rt_cost = 2 * (spread + slippage) * ev.size
        funding_share = position.cumulative_funding
                        * (ev.size / position.size)
        net_pnl = pnl - rt_cost - funding_share
        trades.append(Trade(..., pnl=net_pnl, exit_reason=ev.reason))
        account.close_position(ev.size * ev.price,
                               (spread + slippage) * ev.size)
        position.cumulative_funding -= funding_share
        position.size -= ev.size

      if position.size <= 0:
        position = None
      else:
        # Update trailing stop if post-TP
        if position.tp_50_hit:
          new_trail = position.highest_high - 2 * position.signal_atr
          position.trailing_stop = max(position.trailing_stop, new_trail)
        # Charge overnight funding
        ff = fedfunds_for_date(fedfunds, date)
        funding = (position.entry_price * position.size)
                   * (ff + 0.025) / 365
        position.cumulative_funding += funding
        account.charge_funding(funding)

    # ── Phase 3: Update equity ────────────────────────────────────
    unrealized = 0.0
    if position is not None:
      unrealized = (C - position.entry_price) * position.size
    equity = account.cash + unrealized
    account.update_equity(equity)
    equity_records.append(date, equity, account.drawdown,
                          account.throttle_state)

    # ── Phase 4: New signal ───────────────────────────────────────
    if position is None and pending is None:
      if account.throttle_state != HALTED:
        sig = indicators.loc[date, "signal"]
        if sig in (BUY, STRONG_BUY):
          # Run guards
          if all_guards_pass(guards, guards_enabled, row, eurusd, date,
                             account.drawdown):
            trap = compute_trap_order(row.high, row.atr_14)
            pending = PendingOrder(trap.buy_stop, trap.limit,
                                   row.atr_14, row.adx_14, date)

  equity_curve = DataFrame(equity_records).set_index("date")
  return BacktestResult(equity_curve, trades)
```

## Decisions

- **Costs as cash adjustments**: spread + slippage deducted from cash at entry and exit (not baked into fill/exit prices). Funding deducted daily from cash. This keeps fill/exit prices clean for Trade records.
- **Equity = cash + unrealized**: consistent with production PortfolioManager. Unrealized exit costs (spread/slippage for closing) NOT included in MTM equity — small relative to gold prices.
- **Sizing at fill time**: position sized using current equity when trap order fills (not signal-day equity). Since partial position rule blocks signals while a position is open, equity won't change between signal day and fill day anyway.
- **Guards evaluated at signal time**: trap order carry signal_atr/signal_adx, not re-evaluated at fill time.
- **Trailing stop uses yesterday's value for exit check**: check low vs existing trailing stop first, THEN update trailing stop with today's high. Prevents same-day whipsaw.
- **No SwingSniper dependency**: backtest reads composite/signal directly from the pre-computed indicators DataFrame and runs guards inline. Avoids PortfolioManager I/O.

## File Map

- `src/trading_advisor/backtest/engine.py` — All engine logic: types, account, fill, exits, costs, main loop
- `src/trading_advisor/backtest/report.py` — Performance metrics + Plotly HTML report
- `src/trading_advisor/backtest/__init__.py` — Re-exports
- `tests/test_backtest_types.py` — Trade, BacktestAccount, check_fill tests
- `tests/test_backtest_exits.py` — evaluate_exits tests
- `tests/test_backtest_costs.py` — Cost function tests
- `tests/test_backtest_engine.py` — run_backtest unit tests
- `tests/test_backtest_metrics.py` — compute_metrics tests
- `tests/test_backtest_report.py` — generate_report tests
- `tests/integration/test_backtest_integration.py` — Full engine on synthetic data

## Tasks

### Task 1: Foundation Types + Account Model + Fill Logic
- **Files**: `src/trading_advisor/backtest/engine.py`, `tests/test_backtest_types.py`
- **Action**: Create the foundation types and simple logic in engine.py:
  1. `ExitReason` enum: STOP_LOSS, TAKE_PROFIT, TRAILING_STOP, TIME_STOP
  2. `Trade` frozen dataclass: entry_date, exit_date, entry_price, exit_price, size, direction, pnl, exit_reason, days_held, spread_cost, slippage_cost, funding_cost
  3. `BacktestResult` frozen dataclass: equity_curve (DataFrame), trades (tuple[Trade, ...]), start_date (date), end_date (date), starting_capital (float)
  4. `BacktestAccount` class: cash, high_water_mark, throttle_state, drawdown. Methods: open_position(notional, entry_cost), close_position(proceeds, exit_cost), charge_funding(amount), update_equity(equity) → ThrottleState, property equity_value
  5. `_PendingOrder` frozen dataclass: buy_stop, limit, signal_atr, signal_adx, signal_date
  6. `_ActivePosition` mutable dataclass: entry_price, entry_date, size, original_size, stop_loss, take_profit, signal_atr, tp_50_hit, highest_high, trailing_stop, days_held, cumulative_funding
  7. `check_fill(buy_stop, limit, day_high, day_low) -> bool`
- **Test**: Write tests in `tests/test_backtest_types.py`:
  - Trade construction: `Trade(entry_date=date(2024,1,2), exit_date=date(2024,1,5), entry_price=2050.0, exit_price=2010.0, size=0.05, direction="LONG", pnl=-2.04, exit_reason=ExitReason.STOP_LOSS, days_held=3, spread_cost=0.03, slippage_cost=0.01, funding_cost=0.0)` — verify all fields
  - BacktestAccount initial state: `BacktestAccount(15000.0)` → cash=15000, HWM=15000, drawdown=0.0, throttle=NORMAL
  - BacktestAccount open: start 15000, open_position(notional=102.5, entry_cost=0.02) → cash=14897.48
  - BacktestAccount close: cash=14897.48, close_position(proceeds=103.0, exit_cost=0.02) → cash=15000.46
  - BacktestAccount charge_funding: cash=14897.48, charge_funding(0.02) → cash=14897.46
  - BacktestAccount update_equity: start 15000, update_equity(14000) → HWM=15000, DD=1000/15000=0.0667, throttle=NORMAL; then update_equity(13800) → DD=1200/15000=0.08, throttle=THROTTLED_50
  - BacktestAccount auto_recover: in HALTED state, equity recovers below 8% of HWM → transitions to THROTTLED_50 (not NORMAL)
  - check_fill(2050, 2051.5, day_high=2055, day_low=2045) → True
  - check_fill(2050, 2051.5, day_high=2049, day_low=2040) → False (high < buy_stop)
  - check_fill(2050, 2051.5, day_high=2055, day_low=2052) → False (gap-through: low > limit)
  - check_fill(2050, 2051.5, day_high=2050, day_low=2051.5) → True (exact boundary)
- **Verify**: `uv run pytest tests/test_backtest_types.py -v --no-cov`
- **Done when**: All types construct, account tracks state correctly, check_fill handles all edge cases, all tests pass, mypy clean
- [ ] Completed

### Task 2: Exit Evaluation Logic
- **Files**: `src/trading_advisor/backtest/engine.py` (add to existing), `tests/test_backtest_exits.py`
- **Action**: Add exit evaluation to engine.py:
  1. `ExitEvent` frozen dataclass: price (float), size (float), reason (ExitReason)
  2. `evaluate_exits(position: _ActivePosition, day_high: float, day_low: float, day_close: float) -> list[ExitEvent]`

  Logic (exit priority: SL > TP > trailing > time stop):

  **Pre-TP (tp_50_hit=False):**
  - If day_low <= stop_loss → return [ExitEvent(stop_loss, position.size, STOP_LOSS)] (full exit)
  - Elif day_high >= take_profit → half_size = floor(position.size / 2 * 100) / 100; remaining = position.size - half_size; return [ExitEvent(take_profit, half_size, TAKE_PROFIT)]. Caller must set tp_50_hit=True and position.size=remaining.
  - Elif days_held >= 10 → return [ExitEvent(day_close, position.size, TIME_STOP)] (full exit)
  - Else → return [] (no exit)

  **Post-TP (tp_50_hit=True):**
  - If day_low <= stop_loss → return [ExitEvent(stop_loss, position.size, STOP_LOSS)]
  - Elif trailing_stop > 0 and day_low <= trailing_stop → return [ExitEvent(trailing_stop, position.size, TRAILING_STOP)]
  - Elif days_held >= 10 → return [ExitEvent(day_close, position.size, TIME_STOP)]
  - Else → return []

  Note: The main loop is responsible for updating highest_high and trailing_stop BEFORE calling evaluate_exits on subsequent days. On the TP day itself, trailing stop is NOT checked (it activates on the next day).

- **Test**: Write tests in `tests/test_backtest_exits.py`:
  - **SL hit pre-TP**: position(entry=2050, size=0.10, SL=2010, TP=2120, tp_50_hit=False, days_held=3, trailing=0). day_low=2005 → [ExitEvent(2010, 0.10, STOP_LOSS)]
  - **SL not hit**: same position, day_low=2011 → []
  - **TP hit**: position(entry=2050, size=0.10, SL=2010, TP=2120, tp_50_hit=False, days_held=3). day_high=2125, day_low=2040 → [ExitEvent(2120, 0.05, TAKE_PROFIT)] (half of 0.10 rounded down to 0.05)
  - **SL beats TP** (same candle): position(entry=2050, size=0.10, SL=2010, TP=2120, tp_50_hit=False). day_high=2125, day_low=2005 → [ExitEvent(2010, 0.10, STOP_LOSS)] (SL wins)
  - **Trailing stop hit**: position(entry=2050, size=0.05, SL=2010, TP=2120, tp_50_hit=True, trailing=2090, days_held=7). day_low=2085 → [ExitEvent(2090, 0.05, TRAILING_STOP)]
  - **Trailing not hit**: same, day_low=2091 → []
  - **SL beats trailing**: position(tp_50_hit=True, SL=2010, trailing=2090). day_low=2005 → [ExitEvent(2010, 0.05, STOP_LOSS)]
  - **Time stop pre-TP**: position(tp_50_hit=False, days_held=10, SL=2010, TP=2120). day_high=2050, day_low=2020, day_close=2040 → [ExitEvent(2040, 0.10, TIME_STOP)]
  - **Time stop post-TP**: position(tp_50_hit=True, days_held=10, trailing=2090). day_high=2100, day_low=2091, day_close=2095 → [ExitEvent(2095, 0.05, TIME_STOP)]
  - **Day 9 no time stop**: position(days_held=9) → [] (no exit from time stop alone)
  - **Trailing beats time stop**: position(tp_50_hit=True, trailing=2090, days_held=10). day_low=2085 → [ExitEvent(2090, 0.05, TRAILING_STOP)]
  - **TP half-size rounding**: position(size=0.07, ...) → half = floor(0.07/2*100)/100 = floor(3.5)/100 = 0.03
- **Verify**: `uv run pytest tests/test_backtest_exits.py -v --no-cov`
- **Done when**: All exit scenarios handled, priority rules enforced, half-size rounding correct, tests pass, mypy clean
- [ ] Completed

### Task 3: Cost Model
- **Files**: `src/trading_advisor/backtest/engine.py` (add to existing), `tests/test_backtest_costs.py`
- **Action**: Add cost functions to engine.py:
  1. `compute_round_trip_cost(size: float, spread_per_side: float, slippage_per_side: float) -> tuple[float, float]` — returns (spread_cost, slippage_cost) where spread_cost = 2 * spread_per_side * size, slippage_cost = 2 * slippage_per_side * size
  2. `compute_overnight_funding(position_notional: float, fedfunds_rate: float) -> float` — returns position_notional * (fedfunds_rate + 0.025) / 365. position_notional = entry_price * size.
  3. `_get_fedfunds_rate(fedfunds: pd.Series, date: pd.Timestamp) -> float` — look up the FEDFUNDS rate for the given date. If exact date not in series, use the most recent prior value (forward-fill). If no prior value, use 0.0.
- **Test**: Write tests in `tests/test_backtest_costs.py`:
  - round_trip_cost(size=0.05, spread=0.3, slippage=0.1) → (0.03, 0.01) [spread=2*0.3*0.05=0.03, slip=2*0.1*0.05=0.01]
  - round_trip_cost(size=1.0, spread=0.3, slippage=0.1) → (0.6, 0.2)
  - round_trip_cost(size=0.01, spread=0.3, slippage=0.1) → (0.006, 0.002)
  - overnight_funding(position_notional=102.5, fedfunds_rate=0.05) → 102.5 * 0.075 / 365 = 0.02106164... ≈ 0.021062
  - overnight_funding(position_notional=102.5, fedfunds_rate=0.0) → 102.5 * 0.025 / 365 = 0.007021...
  - overnight_funding(position_notional=0.0, fedfunds_rate=0.05) → 0.0
  - _get_fedfunds_rate: exact date match → returns that value; date not in series → returns most recent prior (ffill); no prior date → returns 0.0
- **Verify**: `uv run pytest tests/test_backtest_costs.py -v --no-cov`
- **Done when**: Cost functions return correct values, fedfunds lookup handles edge cases, tests pass, mypy clean
- [ ] Completed

### Task 4: Main Backtest Loop
- **Files**: `src/trading_advisor/backtest/engine.py` (add run_backtest), `tests/test_backtest_engine.py`
- **Action**: Implement the main backtest function following the pseudocode above. Function signature:
  ```python
  def run_backtest(
      indicators: pd.DataFrame,
      eurusd: pd.DataFrame,
      guards: Sequence[Guard],
      guards_enabled: dict[str, bool],
      fedfunds: pd.Series,
      starting_capital: float = 15000.0,
      spread_per_side: float = 0.3,
      slippage_per_side: float = 0.1,
  ) -> BacktestResult:
  ```

  Required indicator columns: open, high, low, close, atr_14, adx_14, ema_8, sma_50, sma_200, rsi_14, composite, signal.

  Required eurusd columns: close, sma_200.

  The function reuses existing guard infrastructure: `run_guards()` from `trading_advisor.guards.pipeline`, `compute_trap_order`, `compute_stop_loss`, `compute_take_profit`, `compute_position_size`.

  Drawdown throttling uses the same state machine as PortfolioManager._evaluate_throttle with auto_recover=True: HALTED recovers to THROTTLED_50 when DD drops below 8%.

- **Test**: Write unit tests in `tests/test_backtest_engine.py` using synthetic data (no guards, all guards disabled):
  - **No signals**: all composite < 1.5 → empty trades, flat equity curve at 15000
  - **Signal but no fill**: composite = BUY on day 5. Day 6: high < buy_stop → no fill. Verify 0 trades.
  - **Single complete trade (SL exit)**: BUY signal on day 5, fills day 6, SL hit day 8. Verify 1 trade with correct entry/exit/pnl.
  - **Single complete trade (time stop)**: BUY signal, fills, no SL/TP for 10 days → time stop. Verify exit at close.
  - **TP + trailing**: BUY signal, fills, TP hit on day 3, trailing stop hit on day 7. Verify 2 trades (TP half + trailing half).
  - **Equity curve shape**: verify equity_curve has correct columns (equity, drawdown_pct, throttle_state), one row per trading day, monotonically dated.
- **Verify**: `uv run pytest tests/test_backtest_engine.py -v --no-cov`
- **Done when**: Main loop handles all phases correctly, equity tracking consistent, throttle state machine works, tests pass, mypy clean
- [ ] Completed

### Task 5: Performance Metrics
- **Files**: `src/trading_advisor/backtest/report.py`, `tests/test_backtest_metrics.py`
- **Action**: Implement `compute_metrics(result: BacktestResult, fedfunds: pd.Series) -> dict[str, float]` in report.py.

  Metrics to compute:
  - `sharpe_ratio`: annualized. `(mean_daily_excess_return / std_daily_return) * sqrt(252)`. daily_rf = fedfunds_rate / 252 (use mean FEDFUNDS over the period). If std=0, return 0.0.
  - `sortino_ratio`: annualized. Uses downside deviation (std of negative excess returns only). `(mean_daily_excess_return / downside_std) * sqrt(252)`. If no negative returns, return inf.
  - `profit_factor`: sum(winning_pnl) / abs(sum(losing_pnl)). If no losing trades, return inf. If no winning trades, return 0.0.
  - `max_drawdown_pct`: max of equity_curve["drawdown_pct"] column.
  - `max_drawdown_duration`: longest consecutive period where equity < HWM, in trading days.
  - `win_rate`: count(pnl > 0) / total_trades. If no trades, return 0.0.
  - `total_trades`: len(trades).
  - `avg_win`: mean pnl of winning trades. If none, return 0.0.
  - `avg_loss`: mean absolute pnl of losing trades. If none, return 0.0.
  - `avg_win_loss_ratio`: avg_win / avg_loss. If avg_loss=0, return inf.
  - `annualized_return`: (final_equity / starting_capital) ^ (252 / trading_days) - 1.
  - `total_return_pct`: (final_equity - starting_capital) / starting_capital * 100.
  - `avg_days_held`: mean days_held across all trades.
  - `total_costs`: sum of spread + slippage + funding across all trades.

- **Test**: Write tests in `tests/test_backtest_metrics.py` with hand-computed values:
  - **3-trade scenario**: trades with pnl [+100, -50, +75], equity curve starting at 15000 ending at 15125.
    - win_rate = 2/3 = 0.6667
    - avg_win = 87.5
    - avg_loss = 50.0
    - avg_win_loss_ratio = 1.75
    - profit_factor = 175 / 50 = 3.5
    - total_trades = 3
  - **No trades**: empty trade list → win_rate=0, profit_factor=0, total_trades=0
  - **All wins**: 3 trades all positive → profit_factor=inf
  - **All losses**: 3 trades all negative → profit_factor=0, win_rate=0
  - **Sharpe with known returns**: provide a synthetic equity curve with daily values, pre-compute expected Sharpe
  - **Max drawdown duration**: equity curve that dips and recovers → verify duration count
- **Verify**: `uv run pytest tests/test_backtest_metrics.py -v --no-cov`
- **Done when**: All metrics computed correctly, edge cases handled (no trades, all wins, all losses), tests pass, mypy clean
- [ ] Completed

### Task 6: Plotly HTML Report
- **Files**: `src/trading_advisor/backtest/report.py` (add to existing), `tests/test_backtest_report.py`
- **Action**: Implement `generate_report(result: BacktestResult, metrics: dict[str, float]) -> str` that returns a self-contained HTML string with embedded Plotly charts.

  Sections:
  1. **Metrics summary table**: all metrics from compute_metrics, formatted nicely
  2. **Equity curve chart**: Plotly line chart of equity over time
  3. **Drawdown chart**: Plotly area chart of drawdown_pct over time (inverted, red fill)
  4. **Monthly returns heatmap**: rows=years, cols=months, values=monthly return %, color-coded green/red
  5. **Trade log table**: HTML table with entry/exit dates, prices, size, pnl, exit_reason, days_held, costs

  Use `plotly.graph_objects` for charts. Embed as `<div>` with `include_plotlyjs='cdn'` on first chart, False on subsequent. Wrap in a basic HTML template with inline CSS.

- **Test**: Write tests in `tests/test_backtest_report.py`:
  - Output is a non-empty string
  - Output contains `<html>` and `</html>`
  - Output contains "Equity Curve" (chart title)
  - Output contains "plotly" (CDN reference)
  - Output contains metrics values as strings (e.g., the Sharpe ratio value)
  - Output contains trade log entries
  - Handles empty trade list gracefully (report still generates)
- **Verify**: `uv run pytest tests/test_backtest_report.py -v --no-cov`
- **Done when**: Report generates valid HTML with all sections, handles edge cases, tests pass, mypy clean
- [ ] Completed

### Task 7: Integration Test
- **Files**: `tests/integration/test_backtest_integration.py`
- **Action**: Write comprehensive integration tests that run the full backtest engine on synthetic data with known outcomes. These tests verify the entire pipeline end-to-end.

  **Scenario A — Full lifecycle (TP + trailing exit)**:
  Build 30 rows of synthetic OHLCV + indicator data where:
  - Day 5: composite > 1.5 (BUY signal). All guards disabled.
  - Day 6: fill condition met (high >= buy_stop, low <= limit)
  - Day 10: TP hit (high >= take_profit) → 50% close
  - Day 14: trailing stop hit (low <= trailing) → remaining 50% close
  Verify: 2 trades, correct P&L, equity curve consistent with trades, costs deducted.

  **Scenario B — Stop loss exit**:
  Signal and fill, then price drops through SL on day 3 of position.
  Verify: 1 trade, negative P&L, exit_reason=STOP_LOSS.

  **Scenario C — No signals**:
  All composite scores < 1.5.
  Verify: 0 trades, equity stays at starting_capital (minus zero costs).

  **Scenario D — Gap-through rejection**:
  Signal fires, next day price gaps above limit → no fill.
  Verify: 0 trades.

  **Scenario E — Time stop**:
  Fill happens, price meanders for 10 trading days without hitting SL or TP.
  Verify: exit at close on day 10, exit_reason=TIME_STOP.

  **Scenario F — SL + TP same candle**:
  Wide-range candle that triggers both SL and TP conditions.
  Verify: SL wins, full position closed at SL price.

  **Scenario G — Equity consistency**:
  After all trades, verify: starting_capital + sum(trade.pnl) ≈ final equity (within floating point tolerance).

- **Verify**: `uv run pytest tests/integration/test_backtest_integration.py -v --no-cov`
- **Done when**: All scenarios pass, equity consistent, no future data leakage, tests pass, mypy clean
- [ ] Completed

### Task 8: Re-exports + Final Verification
- **Files**: `src/trading_advisor/backtest/__init__.py`
- **Action**: Update __init__.py to re-export public API:
  - From engine: `ExitReason`, `Trade`, `BacktestResult`, `BacktestAccount`, `run_backtest`, `check_fill`, `evaluate_exits`
  - From report: `compute_metrics`, `generate_report`
  Run full verification: `uv run mypy --strict src/` and `uv run pytest --cov --cov-branch --cov-fail-under=100`
- **Test**: Full suite passes with 100% coverage
- **Verify**: `uv run mypy --strict src/ && uv run pytest --cov --cov-branch --cov-fail-under=100`
- **Done when**: mypy clean, 100% coverage, all tests pass
- [ ] Completed
