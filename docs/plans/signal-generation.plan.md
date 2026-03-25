# Plan: Signal Generation (1D)

## Goal

Build the signal generation pipeline: composite score → threshold check → guard evaluation → trap order calculation → position sizing → frozen `TradeSignal` object. This connects the existing composite/guard infrastructure to actionable trade signals. Also includes a historical scanner for spot-checking.

## Decisions

- **Trap order + exits in one module** (`orders.py`): Both are pure functions operating on the same inputs (ATR, ADX, prices). Keeps the module count low.
- **TradeSignal in its own file** (`signal.py`): It's a value object imported by multiple modules (pipeline, scan, future backtest). Avoids circular imports.
- **`generate_signals` returns `list[object]`**: Matches the `Strategy` ABC contract. Internally typed via a private `_evaluate` method returning `TradeSignal | None`.
- **Historical scan ignores portfolio state**: It shows all potential signals (assuming starting capital, no partial positions). The backtest (1E) will simulate actual portfolio evolution.
- **Cash reserve uses current cash, not equity**: Per spec, `remaining_cash >= equity × cash_reserve_pct` after sizing. Cash is the spendable balance; equity includes unrealized P&L.

## File Map

- `src/trading_advisor/strategy/signal.py` — `TradeSignal` frozen dataclass
- `src/trading_advisor/strategy/orders.py` — `compute_trap_order`, `compute_stop_loss`, `compute_take_profit`
- `src/trading_advisor/strategy/sizing.py` — `compute_position_size` (replaces stub)
- `src/trading_advisor/strategy/swing_sniper.py` — `SwingSniper(Strategy)` pipeline (replaces stub)
- `src/trading_advisor/strategy/scan.py` — `scan_signals()` historical scanner
- `src/trading_advisor/strategy/__init__.py` — re-exports
- `tests/test_signal_dataclass.py` — tests for TradeSignal
- `tests/test_orders.py` — tests for trap order + exits
- `tests/test_sizing.py` — tests for position sizing (replaces stub)
- `tests/test_swing_sniper.py` — tests for pipeline
- `tests/test_scan.py` — tests for historical scanner

## Tasks

### Task 1: TradeSignal dataclass (1D.1)
- **Files**: `src/trading_advisor/strategy/signal.py`, `tests/test_signal_dataclass.py`
- **Action**: Create a frozen dataclass `TradeSignal` with fields: `date` (datetime.date), `asset` (str), `direction` (str), `composite_score` (float), `signal_strength` (str), `trap_order_stop` (float), `trap_order_limit` (float), `stop_loss` (float), `take_profit` (float), `trailing_stop_atr_mult` (float), `position_size` (float), `risk_amount` (float), `risk_reward_ratio` (float), `guards_passed` (tuple[str, ...]), `ttl` (int). Add `__post_init__` validation: `position_size > 0`, `stop_loss < trap_order_stop < take_profit`, `ttl > 0`, `risk_amount > 0`, `risk_reward_ratio > 0`. Raise `ValueError` on violation.
- **Test**: Construct valid instance, verify all fields. Test each validation rule triggers ValueError.
- **Verify**: `uv run pytest tests/test_signal_dataclass.py -v --no-cov`
- **Done when**: Dataclass constructs, freezes, validates, mypy passes
- [x] Completed

### Task 2: Trap order + exit calculations (1D.2 + 1D.3)
- **Files**: `src/trading_advisor/strategy/orders.py`, `tests/test_orders.py`
- **Action**: Three pure functions:
  - `compute_trap_order(signal_day_high: float, atr: float) -> tuple[float, float]` — returns (buy_stop, limit). `buy_stop = signal_day_high + 0.02 * atr`, `limit = buy_stop + 0.05 * atr`.
  - `compute_stop_loss(entry_price: float, atr: float) -> float` — returns `entry_price - 2.0 * atr`.
  - `compute_take_profit(entry_price: float, atr: float, adx: float) -> float` — `mult = max(2.5, min(4.5, 2.0 + adx / 30.0))`, returns `entry_price + mult * atr`.
- **Test**: Pre-computed values (see plan below). Each function tested independently.
- **Verify**: `uv run pytest tests/test_orders.py -v --no-cov`
- **Done when**: All functions return exact expected values, mypy passes
- [x] Completed

### Task 3: Position sizing (1D.4)
- **Files**: `src/trading_advisor/strategy/sizing.py`, `tests/test_sizing.py`
- **Action**: Function `compute_position_size(equity: float, cash: float, entry_price: float, atr: float, throttle_state: ThrottleState, num_open_positions: int) -> float`. Steps: (1) determine risk_pct by tier, (2) ATR-based = equity × risk_pct / (atr × 2), (3) Cap-based = equity × 0.15 / entry_price, (4) size = min(ATR, cap), (5) if THROTTLED_50 or THROTTLED_MAX1: halve, (6) if THROTTLED_MAX1 and num_open_positions >= 1: return 0.0, (7) cash reserve check: if cash - size × entry_price < equity × reserve_pct, reduce size to (cash - equity × reserve_pct) / entry_price, (8) floor to 0.01, (9) if < 0.01: return 0.0. Reserve_pct: <5k→40%, 5k-15k→30%, >=15k→25%.
- **Test**: Pre-computed values for each tier, each constraint, throttle halving, cash reserve reduction, minimum lot.
- **Verify**: `uv run pytest tests/test_sizing.py -v --no-cov`
- **Done when**: All sizing edge cases pass, mypy passes
- [x] Completed

### Task 4: Signal generation pipeline (1D.5 + 1D.6)
- **Files**: `src/trading_advisor/strategy/swing_sniper.py`, `tests/test_swing_sniper.py`, `src/trading_advisor/strategy/__init__.py`
- **Action**: `SwingSniper(Strategy)` class. Constructor takes `PortfolioManager`, `Sequence[Guard]`, `dict[str, bool]` (guards_enabled). Method `generate_signals(**kwargs) -> list[object]` extracts `indicators` (DataFrame), `eurusd` (DataFrame), `evaluation_date` (date) from kwargs. Private `_evaluate()` does: (1) get row for date, (2) check signal is BUY/STRONG_BUY, (3) check no open positions (partial rule), (4) run guards, (5) compute trap order, (6) compute SL/TP, (7) compute size, (8) build TradeSignal. Also update `__init__.py` re-exports.
- **Test**: Mock PortfolioManager and guards. Test: below threshold → empty, guard fail → empty, position open → empty, all pass → valid TradeSignal with correct values.
- **Verify**: `uv run pytest tests/test_swing_sniper.py -v --no-cov`
- **Done when**: Pipeline correctly wires all components, mypy passes
- [x] Completed

### Task 5: Historical signal scan (1D.7)
- **Files**: `src/trading_advisor/strategy/scan.py`, `tests/test_scan.py`
- **Action**: Function `scan_signals(indicators: DataFrame, eurusd: DataFrame, guards: Sequence[Guard], guards_enabled: dict[str, bool], event_dates: Sequence[date], starting_equity: float) -> DataFrame`. Iterates each date after warmup, runs composite check + guards + sizing (no portfolio state — assumes fresh capital per signal). Returns DataFrame with columns: date, composite, signal, trap_stop, trap_limit, sl, tp, size.
- **Test**: Synthetic data with known composite values. Verify output shape, column presence, no future data leakage (signal on day T uses only data up to day T).
- **Verify**: `uv run pytest tests/test_scan.py -v --no-cov`
- **Done when**: Scanner produces correct output, mypy passes
- [x] Completed
