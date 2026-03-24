# Plan: Guard System (Task 1C)

## Goal

Implement all 5 safety guards, the guard pipeline runner, and the portfolio manager (for drawdown tracking). Guards gate trade signals — all enabled guards must pass for a signal to fire. Each guard is individually togglable via an `enabled` config dict.

## File Map

- `src/trading_advisor/guards/base.py` — Guard ABC + frozen GuardResult (refinements)
- `src/trading_advisor/guards/pipeline.py` — `run_guards()` function (new)
- `src/trading_advisor/guards/macro_gate.py` — Macro Gate implementation
- `src/trading_advisor/guards/trend_gate.py` — Trend Gate implementation
- `src/trading_advisor/guards/event_guard.py` — Event Guard implementation
- `src/trading_advisor/guards/pullback_zone.py` — Pullback Zone implementation
- `src/trading_advisor/guards/drawdown_gate.py` — Drawdown Gate implementation
- `src/trading_advisor/guards/__init__.py` — Package exports
- `src/trading_advisor/portfolio/manager.py` — Portfolio Manager (state machine, persistence)
- `src/trading_advisor/portfolio/__init__.py` — Package exports
- `tests/test_guards.py` — Unit tests for guards + pipeline
- `tests/test_portfolio.py` — Unit tests for Portfolio Manager (new)
- `tests/integration/test_guard_integration.py` — Integration test (new)

## Tasks

### Task 1: Guard infrastructure — GuardResult frozen + pipeline runner (1C.1 + 1C.2)

- **Files**: `src/trading_advisor/guards/base.py`, `src/trading_advisor/guards/pipeline.py` (new), `tests/test_guards.py`
- **Action**:
  1. Make `GuardResult` a `@dataclass(frozen=True)` in `guards/base.py`.
  2. Create `guards/pipeline.py` with `run_guards(guards, enabled, **kwargs) -> list[GuardResult]`.
     - `guards`: `Sequence[Guard]` — the list of guard instances.
     - `enabled`: `dict[str, bool]` — maps guard name to on/off. Missing key = enabled (default True).
     - `**kwargs`: forwarded to each guard's `evaluate()`.
     - For disabled guards: append `GuardResult(passed=True, guard_name=..., reason="SKIPPED (disabled)")`.
     - For enabled guards: call `guard.evaluate(**kwargs)` and append the result.
  3. Write tests in `tests/test_guards.py`:
     - `GuardResult` construction: `GuardResult(passed=True, guard_name="X", reason="ok")` — verify all fields.
     - `GuardResult` frozen: assigning `result.passed = False` raises `FrozenInstanceError`.
     - `Guard` ABC: instantiating directly raises `TypeError`.
     - Pipeline — all pass: 2 mock guards both pass → `all(r.passed for r in results)` is True.
     - Pipeline — one fails: mock guard A passes, mock guard B fails → `results[1].passed` is False.
     - Pipeline — disabled guard skipped: `enabled={"B": False}`, guard B not called, result has reason containing "SKIPPED".
     - Pipeline — all disabled: empty `enabled` with all guards set to False → all results are SKIPPED, `all(r.passed ...)` is True.
     - Pipeline — missing key defaults to enabled: guard "C" not in `enabled` dict → guard C is called.
- **Verify**: `uv run pytest tests/test_guards.py -v --no-cov`
- **Done when**: GuardResult is frozen, pipeline runner passes all tests, mypy clean.
- [x] Completed

### Task 2: Macro Gate + Trend Gate (1C.3 + 1C.4)

- **Files**: `src/trading_advisor/guards/macro_gate.py`, `src/trading_advisor/guards/trend_gate.py`, `tests/test_guards.py`
- **Action**:
  1. **Macro Gate** (`macro_gate.py`): EUR/USD close > EUR/USD 200 SMA → pass.
     - Extract `eurusd_close` (float) and `eurusd_sma_200` (float) from kwargs.
     - If `eurusd_close > eurusd_sma_200` → pass. Otherwise → fail.
     - Fix docstring: says "DXY" but should say "EUR/USD close > EUR/USD 200 SMA (weak dollar favors gold)".
     - Reason string format: `"EUR/USD {eurusd_close:.4f} {'>' if passed else '<='} 200 SMA ({eurusd_sma_200:.4f})"`.
  2. **Trend Gate** (`trend_gate.py`): ADX(14) > 20 → pass.
     - Extract `adx` (float) from kwargs.
     - If `adx > 20` → pass. Exactly 20 → fail (strict >).
     - Reason string format: `"ADX {adx:.1f} {'>' if passed else '<='} 20"`.
  3. Tests (append to `tests/test_guards.py`):
     - **Macro Gate pass**: `eurusd_close=1.10, eurusd_sma_200=1.05` → passed=True.
     - **Macro Gate fail**: `eurusd_close=1.02, eurusd_sma_200=1.05` → passed=False.
     - **Macro Gate edge (exactly equal)**: `eurusd_close=1.05, eurusd_sma_200=1.05` → passed=False (not strictly >).
     - **Trend Gate pass**: `adx=25.0` → passed=True.
     - **Trend Gate fail**: `adx=15.0` → passed=False.
     - **Trend Gate edge (exactly 20)**: `adx=20.0` → passed=False.
     - **Trend Gate barely pass**: `adx=20.01` → passed=True.
     - Verify `guard_name` is `"MacroGate"` / `"TrendGate"` in results.
     - Verify reason strings contain the actual values.
- **Verify**: `uv run pytest tests/test_guards.py -v --no-cov`
- **Done when**: Both guards implemented, all tests pass, mypy clean.
- [x] Completed

### Task 3: Event Guard + calendar loader (1C.5 + 1C.6)

- **Files**: `src/trading_advisor/guards/event_guard.py`, `tests/test_guards.py`
- **Action**:
  1. The economic calendar JSON already exists at `data/calendars/economic_calendar.json` with keys: `fomc`, `nfp`, `cpi` (each a list of date strings `"YYYY-MM-DD"`). Covers 2020–2026.
  2. **EventGuard** constructor takes `event_dates: Sequence[date]` — a flat list of all event dates (FOMC + NFP + CPI merged). The caller loads the JSON and flattens. This keeps the guard pure (no I/O).
  3. Add a module-level helper `load_calendar(path: Path) -> list[date]` in `event_guard.py` that:
     - Reads the JSON file.
     - Merges all date lists (fomc + nfp + cpi).
     - Parses each string to `datetime.date`.
     - Returns sorted, deduplicated list.
  4. `EventGuard.evaluate(**kwargs)`:
     - Extract `evaluation_date` (date) from kwargs.
     - Check: for every event date, `abs((evaluation_date - event_date).days) > 2` → pass.
     - If any event is within 2 calendar days (inclusive) → fail.
     - 5-day window: 2 before + event day + 2 after.
     - Reason: if fail, name the blocking event date. If pass, "No events within 2 days".
  5. Tests (use synthetic calendar, NOT the real JSON):
     - Create a test calendar with one event on `date(2024, 3, 20)`:
       - `eval=date(2024, 3, 17)` → pass (3 days before).
       - `eval=date(2024, 3, 18)` → fail (2 days before).
       - `eval=date(2024, 3, 19)` → fail (1 day before).
       - `eval=date(2024, 3, 20)` → fail (day of).
       - `eval=date(2024, 3, 21)` → fail (1 day after).
       - `eval=date(2024, 3, 22)` → fail (2 days after).
       - `eval=date(2024, 3, 23)` → pass (3 days after).
     - Multiple events: events on `date(2024, 1, 10)` and `date(2024, 1, 20)`. Eval `date(2024, 1, 15)` → pass (5 days from both).
     - Empty calendar → always passes.
     - `load_calendar` test: write a temp JSON with known dates, verify output is sorted and deduplicated.
- **Verify**: `uv run pytest tests/test_guards.py -v --no-cov`
- **Done when**: EventGuard + load_calendar implemented, all tests pass, mypy clean.
- [x] Completed

### Task 4: Pullback Zone (1C.7)

- **Files**: `src/trading_advisor/guards/pullback_zone.py`, `tests/test_guards.py`
- **Action**:
  1. `PullbackZone.evaluate(**kwargs)`:
     - Extract `close` (float) and `ema_8` (float) from kwargs.
     - `distance = (close - ema_8) / ema_8`
     - If `distance <= 0.02` → pass. Negative distance passes (intentional: below EMA = not chasing).
     - Reason string: `"Pullback distance {distance:.4f} ({'<=' if passed else '>'} 0.02)"`.
  2. Tests:
     - **Pass (small positive)**: close=2050, ema_8=2030 → distance = 20/2030 ≈ 0.00985 → pass.
     - **Fail (extended)**: close=2100, ema_8=2030 → distance = 70/2030 ≈ 0.03448 → fail.
     - **Edge (exactly 2%)**: close=2070.6, ema_8=2030 → distance = 40.6/2030 = 0.02 exactly → pass (<=).
     - **Pass (negative distance)**: close=2000, ema_8=2030 → distance = -30/2030 ≈ -0.01478 → pass.
     - Verify reason string contains the distance value.
- **Verify**: `uv run pytest tests/test_guards.py -v --no-cov`
- **Done when**: PullbackZone implemented, all tests pass, mypy clean.
- [x] Completed

### Task 5: Portfolio Manager (1C.8)

- **Files**: `src/trading_advisor/portfolio/manager.py`, `src/trading_advisor/portfolio/__init__.py`, `tests/test_portfolio.py` (new)
- **Action**:
  1. Define `ThrottleState` enum: `NORMAL`, `THROTTLED_50`, `THROTTLED_MAX1`, `HALTED`.
  2. Define `Position` frozen dataclass: `symbol: str`, `entry_price: float`, `size: float`, `entry_date: date`, `stop_loss: float`, `take_profit: float`, `signal_atr: float`, `is_partial: bool` (default False), `highest_high: float` (default 0.0, for trailing stop tracking).
  3. Define `PortfolioState` frozen dataclass: `cash: float`, `positions: tuple[Position, ...]` (tuple for immutability), `high_water_mark: float`, `throttle_state: ThrottleState`, `closed_trades: tuple[dict[str, object], ...]`.
  4. Implement `PortfolioManager` class:
     - Constructor: `__init__(self, storage: StorageBackend, storage_key: str = "state/portfolio", auto_recover: bool = False)`.
     - `auto_recover=True` for backtesting (HALTED auto-recovers when DD < 8%).
     - **State persistence**: `_load() -> PortfolioState` reads from storage (returns default if missing), `_save(state: PortfolioState) -> None` writes to storage.
     - `state` property returns current `PortfolioState`.
     - `equity` property: `state.cash + sum(p.size * current_price for p in state.positions)`. For simplicity in the guard context, equity is tracked explicitly: `state.cash` represents total equity when no positions are open.
     - `get_drawdown() -> float`: `(hwm - equity) / hwm` if hwm > 0, else 0.0. Where equity = cash + mark-to-market of positions.
     - `get_throttle_state() -> ThrottleState`: returns `state.throttle_state`.
     - **`update_equity(equity: float) -> ThrottleState`**: The main state-machine driver.
       - Update HWM: `hwm = max(state.high_water_mark, equity)`.
       - Calculate DD: `dd = (hwm - equity) / hwm` if hwm > 0 else 0.0.
       - Evaluate next throttle state (see state machine below).
       - Save updated state. Return new throttle state.
     - **`open_position(position: Position) -> None`**: Add position to state, deduct notional from cash.
     - **`close_position(symbol: str, exit_price: float, size: float) -> float`**: Remove/reduce position, add proceeds to cash, record closed trade. Return P&L.
     - **`resume_from_halted() -> ThrottleState`**: Only callable when HALTED. Evaluate current DD → place in correct state:
       - DD ≥ 15% → stay HALTED (too deep)
       - DD ≥ 12% → THROTTLED_MAX1
       - DD ≥ 6% → THROTTLED_50 (conservative: above NORMAL recovery threshold)
       - DD < 6% → NORMAL
  5. **State machine** for `update_equity`:
     ```
     # Escalation (current state doesn't matter):
     DD ≥ 15% → HALTED
     DD ≥ 12% → THROTTLED_MAX1
     DD ≥ 8%  → THROTTLED_50 (unless already at THROTTLED_MAX1 or HALTED)

     # When DD < 8%, recovery depends on current state:
     HALTED + auto_recover → THROTTLED_50  (backtest only)
     HALTED + !auto_recover → HALTED       (production, needs /resume)
     THROTTLED_MAX1 → THROTTLED_50         (one step down)
     THROTTLED_50 + DD < 6% → NORMAL
     THROTTLED_50 + DD ≥ 6% → THROTTLED_50 (hysteresis)
     NORMAL → NORMAL

     # When 8% ≤ DD < 12%, stay at current if higher:
     THROTTLED_MAX1 → THROTTLED_MAX1       (not yet recovered)
     HALTED → HALTED                       (not yet recovered)
     ```
  6. **Serialization**: PortfolioState to/from dict for JSON storage.
     - Position: date → ISO string, enum → string.
     - PortfolioState: positions tuple → list of dicts, throttle_state → string.
  7. **Tests** (in `tests/test_portfolio.py`). Use `LocalStorage(tmp_path)` for all tests.
     - **Construction + defaults**: new manager with empty storage → cash=0, HWM=0, NORMAL, no positions.
     - **Update equity — no escalation**: equity=15000, HWM starts at 0 → HWM=15000, DD=0, NORMAL.
     - **Escalation NORMAL → THROTTLED_50**: HWM=15000, equity=13800 → DD=8% → THROTTLED_50.
     - **Escalation THROTTLED_50 → THROTTLED_MAX1**: HWM=15000, equity=13200 → DD=12%.
     - **Escalation THROTTLED_MAX1 → HALTED**: HWM=15000, equity=12750 → DD=15%.
     - **Recovery THROTTLED_MAX1 → THROTTLED_50**: HWM=15000, equity=13950 → DD=7% (< 8%) → THROTTLED_50.
     - **Recovery THROTTLED_50 → NORMAL**: HWM=15000, equity=14250 → DD=5% (< 6%) → NORMAL.
     - **Hysteresis: THROTTLED_50 stays at DD=7%**: HWM=15000, equity=13950 → DD=7% (≥ 6%) → stays THROTTLED_50.
     - **THROTTLED_MAX1 stays at DD=9%**: HWM=15000, equity=13650 → DD=9% (≥ 8%) → stays THROTTLED_MAX1.
     - **HALTED stays without auto_recover**: auto_recover=False, DD drops to 5% → still HALTED.
     - **HALTED auto-recovers in backtest**: auto_recover=True, DD drops below 8% → THROTTLED_50.
     - **Resume from HALTED**: DD=12% → THROTTLED_MAX1. DD=7% → THROTTLED_50. DD=4% → NORMAL.
     - **Resume when not HALTED raises error**.
     - **Open position**: adds to positions, deducts from cash.
     - **Close position**: removes position, adds proceeds, records trade.
     - **Persistence roundtrip**: save state, create new manager with same storage, verify state matches.
     - **HWM only ratchets up**: equity goes up then down, HWM stays at peak.
- **Verify**: `uv run pytest tests/test_portfolio.py -v --no-cov`
- **Done when**: Full Portfolio Manager with state machine, persistence, all tests pass, mypy clean.
- [x] Completed

### Task 6: Drawdown Gate (1C.9)

- **Files**: `src/trading_advisor/guards/drawdown_gate.py`, `tests/test_guards.py`
- **Action**:
  1. `DrawdownGate` constructor takes `portfolio_manager: PortfolioManager`.
  2. `evaluate(**kwargs)`:
     - Get drawdown from portfolio manager: `dd = self._portfolio_manager.get_drawdown()`.
     - `dd < 0.15` → pass. `dd >= 0.15` → fail.
     - This is equivalent to checking throttle_state != HALTED, but we check the number directly for clarity.
     - Reason: `"Drawdown {dd:.1%} {'<' if passed else '>='} 15%"`.
  3. Tests:
     - **Pass (no drawdown)**: DD=0% → pass.
     - **Pass (moderate drawdown)**: DD=14.9% → pass.
     - **Fail (at threshold)**: DD=15% → fail.
     - **Fail (deep drawdown)**: DD=20% → fail.
     - Use a mock or stub PortfolioManager that returns known DD values.
- **Verify**: `uv run pytest tests/test_guards.py -v --no-cov`
- **Done when**: DrawdownGate implemented, all tests pass, mypy clean.
- [x] Completed

### Task 7: Integration test + package exports (1C.10)

- **Files**: `tests/integration/test_guard_integration.py` (new), `src/trading_advisor/guards/__init__.py`, `src/trading_advisor/portfolio/__init__.py`
- **Action**:
  1. Update `guards/__init__.py` exports: `Guard`, `GuardResult`, `run_guards`, `MacroGate`, `TrendGate`, `EventGuard`, `PullbackZone`, `DrawdownGate`, `load_calendar`.
  2. Update `portfolio/__init__.py` exports: `PortfolioManager`, `PortfolioState`, `Position`, `ThrottleState`.
  3. Integration test scenarios (use synthetic data, no real API calls):
     - **All guards pass**: EUR/USD above 200 SMA, ADX > 20, no events near, pullback < 2%, DD < 15% → pipeline returns all passed.
     - **Single guard fails**: ADX=18 → TrendGate fails, others pass. Pipeline result has 1 failure.
     - **Multiple guards fail**: ADX=18 + pullback=3% → 2 failures.
     - **Disabled guard skipped**: Disable MacroGate → result shows SKIPPED for MacroGate, others evaluated.
     - **All disabled → all pass**: Every guard disabled → all SKIPPED, signal valid.
     - Verify reason strings are informative (contain actual values).
- **Verify**: `uv run pytest tests/integration/test_guard_integration.py -v --no-cov`
- **Done when**: Integration test passes, exports work, full `uv run mypy --strict src/` and `uv run pytest --cov --cov-branch --cov-fail-under=100` pass.
- [x] Completed
