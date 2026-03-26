# Plan: Walk-Forward & Validation (Task 1F)

## Goal

Implement the complete statistical validation suite for the WealthOps backtest engine: walk-forward analysis with WFE, Monte Carlo bootstrap, shuffled-price test, t-statistic, parameter sensitivity tests, guard ablation, and a GO/NO-GO report that checks kill conditions.

## Decisions

- **BacktestParams before validation**: The engine needs parameterization (ATR mult, TP clamp, fill price, composite threshold) before sensitivity tests can run. Added as Task 1 prerequisite.
- **Composite threshold in engine**: Instead of reclassifying the signal column, the engine reads the raw `composite` column and compares against `BacktestParams.composite_buy_threshold`. Cleaner for sensitivity sweeps.
- **Single atr_multiplier**: SL and trailing stop both use the same ATR multiplier (2x). Sensitivity test 1F.7 varies this single value.
- **Sensitivity recomputes indicators when needed**: Momentum lookback (1F.9) and EMA periods (1F.10) require full indicator recomputation from raw OHLCV. Other sensitivity tests only need engine param changes.
- **Shuffled-price test configurable count**: Default 1000 shuffles for production, but configurable for fast unit tests (n=10).
- **validation.py handles 1F.1-1F.5**: Walk-forward, Monte Carlo, shuffled-price, t-stat all in one module.
- **sensitivity.py handles 1F.6-1F.12**: All parameter sweeps and guard ablation in one module.
- **go_nogo.py handles 1F.13**: Compiles results from validation + sensitivity into pass/fail criteria.

## File Map

- `src/trading_advisor/backtest/engine.py` — add BacktestParams, parameterize run_backtest
- `src/trading_advisor/backtest/validation.py` — walk-forward, Monte Carlo, shuffled-price, t-stat
- `src/trading_advisor/backtest/sensitivity.py` — parameter sensitivity + guard ablation (NEW)
- `src/trading_advisor/backtest/go_nogo.py` — GO/NO-GO report compiler (NEW)
- `src/trading_advisor/backtest/__init__.py` — update exports
- `tests/test_backtest_validation.py` — tests for validation module (NEW)
- `tests/test_backtest_sensitivity.py` — tests for sensitivity module (NEW)
- `tests/test_backtest_go_nogo.py` — tests for GO/NO-GO module (NEW)

## Tasks

### Task 1: BacktestParams + engine parameterization
- **Files**: `src/trading_advisor/backtest/engine.py`, `tests/test_backtest_engine.py`
- **Action**: Add `BacktestParams` frozen dataclass with 5 fields (atr_multiplier, tp_clamp_min, tp_clamp_max, fill_price_offset, composite_buy_threshold). Modify `run_backtest` to accept `params: BacktestParams | None = None` (defaults to `BacktestParams()` if None). Change SL/TP/trailing/fill/signal logic to use params. Add tests for non-default params.
- **Test**: Existing tests still pass with default params. New tests verify: (1) custom ATR mult changes SL price, (2) custom TP clamp changes TP price, (3) fill_price_offset=0.5 fills at midpoint, (4) custom composite threshold changes signal sensitivity.
- **Verify**: `uv run pytest tests/test_backtest_engine.py tests/test_backtest_exits.py tests/test_backtest_costs.py tests/integration/test_backtest_integration.py -v --no-cov`
- **Done when**: All existing backtest tests pass unchanged, new param tests pass, mypy clean.
- [x] Completed

### Task 2: Walk-forward framework + WFE (1F.1 + 1F.2)
- **Files**: `src/trading_advisor/backtest/validation.py`, `tests/test_backtest_validation.py`
- **Action**: Implement walk-forward window generation, per-window backtest execution, Sharpe extraction, and WFE computation. WFE = mean(OOS Sharpe) / mean(IS Sharpe).
- **Test**: Window slicing on synthetic data (verify dates, counts). WFE with known Sharpes.
- **Verify**: `uv run pytest tests/test_backtest_validation.py -v --no-cov`
- **Done when**: Walk-forward generates correct windows, WFE formula verified.
- [x] Completed

### Task 3: Monte Carlo bootstrap + t-statistic (1F.3 + 1F.5)
- **Files**: `src/trading_advisor/backtest/validation.py`, `tests/test_backtest_validation.py`
- **Action**: Implement Monte Carlo resampling of trade P&Ls to build terminal equity distribution, and t-statistic computation. Monte Carlo: resample with replacement, accumulate P&L, repeat 10,000 times, report 5th percentile.
- **Test**: Known trade returns → verify percentile and t-stat values.
- **Verify**: `uv run pytest tests/test_backtest_validation.py -v --no-cov`
- **Done when**: Monte Carlo percentile correct for known inputs, t-stat formula verified.
- [x] Completed

### Task 4: Shuffled-price test (1F.4)
- **Files**: `src/trading_advisor/backtest/validation.py`, `tests/test_backtest_validation.py`
- **Action**: Implement shuffled-price test: permute daily returns, reconstruct price series, recompute indicators + composite, run backtest, collect Sharpe. Repeat n times. Report p-value.
- **Test**: Verify shuffling preserves return distribution (mean, std) but destroys autocorrelation. Verify p-value computation.
- **Verify**: `uv run pytest tests/test_backtest_validation.py -v --no-cov`
- **Done when**: Shuffled-price test runs, p-value computed correctly.
- [x] Completed

### Task 5: Parameter sensitivity + guard ablation (1F.6-1F.12)
- **Files**: `src/trading_advisor/backtest/sensitivity.py`, `tests/test_backtest_sensitivity.py`
- **Action**: Implement sensitivity runners for: composite threshold (1F.6), ATR mult (1F.7), TP clamp (1F.8), momentum lookback (1F.9), EMA periods (1F.10), fill price (1F.11), guard ablation (1F.12). Each returns list of (param_value, metrics_dict).
- **Test**: Verify each runner produces correct number of results, metrics dict has expected keys.
- **Verify**: `uv run pytest tests/test_backtest_sensitivity.py -v --no-cov`
- **Done when**: All 7 sensitivity/ablation functions work, return structured results.
- [x] Completed

### Task 6: GO/NO-GO report (1F.13)
- **Files**: `src/trading_advisor/backtest/go_nogo.py`, `tests/test_backtest_go_nogo.py`
- **Action**: Implement criteria evaluation against kill conditions (Sharpe > 0.5, WFE > 50%, Monte Carlo 5th pct > starting capital, shuffled p < 0.01, t-stat > 2.0, max DD < 20%, win rate 35-75%, total trades > 100). Return structured report with per-criterion pass/fail and overall GO/NO-GO verdict.
- **Test**: All-pass scenario → GO, each individual failure → NO-GO, boundary values.
- **Verify**: `uv run pytest tests/test_backtest_go_nogo.py -v --no-cov`
- **Done when**: GO/NO-GO report evaluates all criteria correctly.
- [x] Completed

### Task 7: Package exports update
- **Files**: `src/trading_advisor/backtest/__init__.py`
- **Action**: Add exports for all new public types and functions from validation.py, sensitivity.py, go_nogo.py.
- **Verify**: `uv run mypy --strict src/`
- **Done when**: All new public API exported, mypy clean.
- [x] Completed
