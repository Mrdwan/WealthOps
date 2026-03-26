# WealthOps — Phase 1 Plan

> **Single source of truth.** Strategy rules, formulas, and build tasks. For system architecture and deployment, see `Architecture.md`. For coding standards, see `CODING_STANDARDS.md`.

---

## Strategy Overview

Phase 1: Gold (XAU/USD) swing trading advisory bot. Long only. Daily candles. 3–10 trading day hold period. Manual execution on IG spread betting (tax-free in Ireland). Starting capital: €15,000.

The system runs at 23:00 UTC after the daily candle closes. It calculates a momentum composite score, checks safety guards, and if conditions align, sends a trade signal via Telegram. It does not execute trades.

---

## The Momentum Composite

Five components (volume excluded for gold), each z-score normalized over a rolling 252 trading-day window, combined as a weighted sum.

### Component 1: Momentum (Weight: 44%)

```
momentum_raw = (close[t-21] / close[t-126]) - 1
```

6-month return (126 trading days), skip most recent month (21 trading days). Z-score over rolling 252-day window.

### Component 2: Trend Confirmation (Weight: 22%)

```
trend_raw = 0
if close > SMA_50:  trend_raw += 1
if close > SMA_200: trend_raw += 1
if SMA_50 > SMA_200: trend_raw += 1
# trend_raw is 0, 1, 2, or 3
```

Uses SMA (Simple Moving Average), not EMA. Z-score over rolling 252-day window.

### Component 3: RSI Filter (Weight: 17%)

```
rsi_raw = 50 - abs(RSI_14 - 50)
```

Produces 0 to 50. Maximum at RSI=50 (neutral). Penalizes overbought (>70) and oversold (<30) equally. Z-score over rolling 252-day window.

### Component 4: ATR Volatility (Weight: 11%)

```
atr_percentile = percentile_rank(ATR_14, rolling 252-day window)  # 0 to 100
atr_raw = 1 - abs(atr_percentile - 50) / 50
```

Produces 0.0 to 1.0. Maximum at 50th percentile (moderate volatility). Penalizes both extremes. Z-score over rolling 252-day window.

### Component 5: Support/Resistance Proximity (Weight: 6%)

```
sr_raw = 1 - (high_20d - close) / close
```

Higher = closer to the 20-day high (breakout territory). Only measures upside proximity for a long-only strategy. Z-score over rolling 252-day window. If ablation study shows no value, drop this component.

### Assembly

```
composite = (momentum_z × 0.44) + (trend_z × 0.22) + (rsi_z × 0.17) + (atr_z × 0.11) + (sr_z × 0.06)
```

### Signal Classification

```
STRONG_BUY  = composite > 2.0σ
BUY         = composite > 1.5σ
NEUTRAL     = between -1.5σ and 1.5σ
SELL        = composite < -1.5σ
STRONG_SELL = composite < -2.0σ
```

Phase 1 is long only. SELL and STRONG_SELL are logged for context but do not trigger signals. Only BUY and STRONG_BUY proceed to the guard pipeline.

---

## Feature Vector

14 features, all calculated on the completed daily candle (23:00 UTC close):

| # | Feature | Formula | Used By |
|---|---------|---------|---------|
| 1 | RSI(14) | Wilder's RSI | RSI composite component |
| 2 | EMA_8 | 8-period EMA | Pullback Zone guard |
| 3 | EMA_20 | 20-period EMA | EMA Fan |
| 4 | EMA_50 | 50-period EMA | EMA Fan |
| 5 | SMA_50 | 50-period SMA | Trend composite component |
| 6 | SMA_200 | 200-period SMA | Trend composite component |
| 7 | MACD Histogram | (EMA_12 - EMA_26) - Signal_9 | Analysis |
| 8 | ADX(14) | Average Directional Index | Trend Gate guard, TP scaling |
| 9 | ATR(14) | Average True Range | Sizing, stops, TP, trail, trap order |
| 10 | Upper Wick Ratio | (High - max(Open,Close)) / (High - Low) | Analysis |
| 11 | Lower Wick Ratio | (min(Open,Close) - Low) / (High - Low) | Analysis |
| 12 | EMA Fan | Boolean: EMA_8 > EMA_20 > EMA_50 | Analysis |
| 13 | Distance from 20d Low | (Close - min(Low, 20d)) / Close | Analysis |
| 14 | Relative Strength vs USD | Rolling 20d z-score of XAU/EUR-USD ratio | Analysis |

Edge cases: `(High - Low) == 0` → both wick ratios = 0.0. Insufficient history (< 252 days) → composite returns NaN, no signal.

---

## Guards

Signal fires only if composite is BUY or STRONG_BUY AND all enabled guards pass. Each guard returns `GuardResult(passed: bool, guard_name: str, reason: str)`. Guards are individually togglable via `GUARDS_ENABLED` config.

**Guard 1 — Macro Gate:** EUR/USD close > EUR/USD 200 SMA → pass. The 200 SMA is on EUR/USD data, not gold. Weak dollar = gold bullish.

**Guard 2 — Trend Gate:** ADX(14) > 20 → pass. Below 20 = ranging market, don't trade.

**Guard 3 — Event Guard:** No FOMC/NFP/CPI within 2 calendar days in either direction → pass. This is a 5-calendar-day exclusion window: 2 before + event day + 2 after. Reads from manually maintained `economic_calendar.json`.

**Guard 4 — Pullback Zone:** `(Close - EMA_8) / EMA_8 <= 0.02` → pass. Negative distance passes intentionally (below EMA = not chasing). Before committing to 2%, validate against historical distribution.

**Guard 5 — Drawdown Gate:** Portfolio drawdown < 15% → pass. This guard only checks the 15% halt. The 8% and 12% throttling levels are applied in position sizing, not here.

---

## Entry: Trap Order

Calculated using the signal day's completed candle and ATR:

```
buy_stop = signal_day_high + (0.02 × ATR_14)
limit    = buy_stop + (0.05 × ATR_14)
```

Placed for the next trading session. Expires at next 23:00 UTC (~24h).

**Fill condition:**
```
filled = (next_day_high >= buy_stop) AND (next_day_low <= limit)
fill_price = buy_stop
```

If the fill condition fails, the order expires. There is no separate gap-through rule — the fill condition already rejects gap-throughs (if price gaps past the limit and the low stays above it, `low <= limit` fails naturally).

---

## Exit Rules

All exit parameters use the signal day's ATR and ADX, fixed at entry. Exits evaluated daily at close.

**Stop Loss:** `entry_price - (2 × signal_day_ATR_14)`. Fixed. Never moves. Applies to full position.

**Take Profit (50% close):**
```
tp_multiplier = clamp(2 + signal_day_ADX / 30, 2.5, 4.5)
take_profit = entry_price + (tp_multiplier × signal_day_ATR_14)
```
Close 50% at TP. Remaining 50% switches to trailing stop.

Note: With Trend Gate requiring ADX > 20, the practical minimum multiplier is ~2.67, so the 2.5 floor rarely fires during normal operation. However, the 2.5 floor is needed during guard ablation testing (1F.11) when the Trend Gate is disabled and ADX can be below 20.

**Trailing Stop (remaining 50% only):** Activates only after TP is hit. Before TP, the full position is protected by the fixed stop loss.
```
trailing_stop = highest_high_since_entry - (2 × signal_day_ATR_14)
```
Updated once per day at close. Only ratchets up, never down.

**Time Stop:** Close entire remaining position at close price after 10 trading days (not calendar days).

**Exit Priority (same-day conflicts):** SL (1st) > TP (2nd) > Trailing (3rd) > Time stop (4th). If SL and TP both trigger on same candle, SL wins (conservative assumption).

**Partial Position Rule:** While trailing the remaining 50%, no new entry signals are taken.

---

## Position Sizing

### Dual Constraint

```
atr_based_size = (equity × risk_pct) / (ATR_14 × 2)
cap_based_size = (equity × 0.15) / entry_price
position_size  = min(atr_based_size, cap_based_size)
```

`equity` = cash + unrealized P&L. `0.15` = maximum 15% notional exposure per position.

`risk_pct` by capital tier:

| Equity | Risk/Trade | Max Positions | Cash Reserve |
|--------|-----------|---------------|--------------|
| < €5,000 | 1.0% | 3 | 40% minimum |
| €5,000–€15,000 | 1.5% | 4 | 30% minimum |
| ≥ €15,000 | 2.0% | 5 | 25% minimum |

Phase 1: max positions = 1. Starting at €15,000 tier (2% risk = €300/trade).

### Cash Reserve

After sizing, verify `remaining_cash >= equity × cash_reserve_pct`. Reduce size if violated. If minimum lot (0.01) still violates, don't trade.

### Drawdown Throttling

Applied in the sizing module. Four states with hysteresis recovery:

| State | Trigger | Effect | Recovery |
|-------|---------|--------|----------|
| NORMAL | Default / DD < 6% | Full sizes | — |
| THROTTLED_50 | DD ≥ 8% | Sizes halved | DD < 6% → NORMAL |
| THROTTLED_MAX1 | DD ≥ 12% | Sizes halved AND max 1 position | DD < 8% → THROTTLED_50 (not NORMAL) |
| HALTED | DD ≥ 15% | No trading (Drawdown Gate blocks) | `/resume` or backtest auto-recovery (see below) |

Each throttle level is strictly more restrictive than the one below it. THROTTLED_MAX1 inherits the halved sizing from THROTTLED_50 and adds the max-1-position constraint.

Recovering from THROTTLED_MAX1 goes to THROTTLED_50 first, not NORMAL. Throttling is active during backtesting.

**`/resume` does not blindly reset to NORMAL.** It evaluates the current drawdown and places the system in the correct state: DD ≥ 12% → THROTTLED_MAX1, DD ≥ 8% → THROTTLED_50, DD < 6% → NORMAL. This preserves the hysteresis design.

**Backtest HALTED recovery:** When DD drops below 8%, the system transitions to THROTTLED_50 (not NORMAL). From there, normal hysteresis applies (DD < 6% → NORMAL). This matches the `/resume` behavior in production.

---

## Lookahead Bias Prevention

Signals are generated after the daily candle closes (23:00 UTC). All calculations use the completed candle and prior history. Trap order is placed for the next session. No future data is ever used.

---

## Backtest Parameters

- Starting capital: €15,000. No monthly additions. Tax: 0%. Profits reinvested.
- Spread: 0.3 pts/side. Slippage: 0.1 pts/side. Overnight funding: IG's published formula (~2.5% annualized for longs, per night held). Look up IG's actual formula before implementing.
- Risk-free rate for Sharpe: FEDFUNDS from FRED data (not 0).

### Output Metrics

| Metric | Minimum | Overfitting Red Flag |
|--------|---------|---------------------|
| Sharpe | > 0.5 | > 3.0 |
| Profit Factor | > 1.2 | > 2.5 |
| Max Drawdown | < 20% | < 5% |
| Win Rate | > 35% | > 75% |
| Total Trades | > 100 | — |

Plus: annualized return, Sortino, avg win/loss ratio, max DD duration, equity curve, monthly heatmap, trade log.

---

## Validation

**Walk-Forward Analysis** (fixed parameters, not optimization): 3-year expanding train, 6-month test, 6-month roll. WFE = mean(OOS Sharpe) / mean(in-sample Sharpe). Pass: >50%. Caution: 30–50%. Fail: <30%.

**Monte Carlo Bootstrap:** 10,000 resamples of trade returns. 5th percentile terminal equity must be > starting capital.

**Shuffled-Price Test:** Permute daily returns, re-run strategy 1,000+ times. Real Sharpe must be > 99th percentile of shuffled distribution (p < 0.01).

**t-statistic:** `mean_trade_return × √N / std_trade_return > 2.0`.

**Parameter Sensitivity:** Test composite threshold (1.0σ–2.5σ), ATR mult (1.5–3.0), TP mult (2.0–5.0), momentum lookback (3M/6M/9M/12M), EMA periods (8/20/50, 10/21/55, 12/26/50). Look for wide plateaus.

**Guard Ablation:** Disable each guard individually, compare Sharpe/DD/trade count vs baseline.

---

## Kill Conditions

| Condition | Action |
|-----------|--------|
| Sharpe < 0.3 after tuning | No edge. Try different approach. |
| Shuffled-price p > 0.05 | Signal is noise. Redesign composite. |
| WFE < 30% | Overfit. Simplify. |
| Win rate > 75% | Overfit. Investigate. |
| < 50 trades in 5 years | Not enough data. |

---

## Decisions Log

| Decision | Rationale |
|----------|-----------|
| S/R only measures proximity to 20d high | Rewarding proximity to 20d low would encourage longs at bearish breakdowns. |
| No vectorbt | Trap order logic too custom. Write backtest with pandas. |
| SMA for 50/200 (not EMA) | Convention. "200 DMA" means SMA. |
| No separate gap-through rule | Fill condition handles it. |
| Walk-forward analysis, not optimization | Fixed params. Optimization increases overfit risk. |
| FEDFUNDS as risk-free rate | Already fetching from FRED. 0 understates hurdle. |
| S/R uses rolling min/max proximity | Simple, no volume needed. 6% weight. |
| Trail activates after TP only | Before TP, fixed SL protects full position. |
| Drawdown gate = 15% halt only | 8%/12% throttling in sizing module. |
| Portfolio = total equity for sizing | Cash + unrealized P&L. Standard. |
| Event guard = 5-day window | 2 before + day + 2 after. Both directions. |
| Time stop = 10 trading days | Not calendar days. Matches hold period. |
| Negative pullback distance passes | Below EMA = not chasing. Intentional. |
| /resume evaluates current DD | Blindly resetting to NORMAL would bypass hysteresis. |
| THROTTLED_MAX1 inherits halved sizing | Each level must be strictly more restrictive. |
| Backtest HALTED recovers to THROTTLED_50 | Matches /resume behavior. Not straight to NORMAL. |
| TP clamp floor 2.5 kept despite ADX > 20 gate | Needed during guard ablation when Trend Gate disabled. |
| Fill price sensitivity test added | 0.05 × ATR fill range >> 0.1 pts slippage. Must verify edge survives adverse fills. |

---

## Current Status

**Active task:** Task 1G (Telegram Bot)
**Blockers:** Awaiting 1F.13 GO decision on real data
**Last updated:** 2026-03-25

---

## Task Checklist

### Task 0: Project Foundation

Everything depends on these. Build before any feature work.

- [ ] **0.1 — Pre-commit + CI**
  - `.pre-commit-config.yaml`: ruff check + fix, ruff format, mypy --strict, pytest --cov --cov-branch
  - GitHub Actions: same checks, Python 3.12+ matrix
  - Test directories: `tests/unit/`, `tests/integration/`

- [ ] **0.2 — StorageBackend ABC + LocalStorage**
  - `storage/base.py`: `StorageBackend` ABC with `read_parquet`, `write_parquet`, `read_json`, `write_json`
  - `storage/local.py`: `LocalStorage`, reads/writes to `WEALTHOPS_DATA_DIR` (default `./data`)
  - Auto-create directories. Missing file → clear error.
  - Unit tests: write/read parquet, write/read JSON, missing file, directory creation

- [ ] **0.3 — Config module**
  - `config.py`: load `WEALTHOPS_*` env vars via python-dotenv
  - Instantiate correct StorageBackend from `WEALTHOPS_STORAGE`
  - Validate required vars (API keys, Telegram tokens). Fail fast if missing.
  - `GUARDS_ENABLED` config dict
  - Unit tests: mock env → correct backend, missing var → ValueError

- [ ] **0.4 — Logging setup**
  - Rotating file handler: 5MB/file, keep 5, write to `logs/wealthops.log`
  - Levels: INFO (success), WARNING (anomalies), ERROR (failures)
  - Unit tests: log file created, rotation works

- [ ] **0.5 — Custom exceptions**
  - `exceptions.py`: `DataValidationError`, `InsufficientHistoryError`, `ConfigurationError`, `StorageError`, `APIError`
  - Unit tests: each exception raises with message

- [ ] **0.6 — Migrate 1A to StorageBackend**
  - Refactor data pipeline to use injected `StorageBackend` instead of direct file I/O
  - All data providers receive `StorageBackend` via constructor
  - Integration test: data pipeline works with `LocalStorage`
  - Skip if 1A already uses StorageBackend

---

### Task 1A: Data Pipeline ✅

- [x] Tiingo API integration (XAU/USD daily OHLCV)
- [x] EUR/USD daily data (Tiingo forex, for Macro Gate)
- [x] FRED integration (VIX, T10Y2Y, FEDFUNDS)
- [x] OHLCV validation rules (high >= low, no nulls, no gaps, etc.)
- [x] Parquet storage with incremental updates
- [x] Bootstrap script for historical data (5-10 years)
- [x] Verify: row counts, date ranges, no gaps on trading days

---

### Task 1B: Indicators & Composite

#### Technical Indicators

- [x] **1B.1 — RSI(14)**
  - Wilder's RSI in `indicators/technical.py`
  - First indicator — establishes module structure and test patterns
  - Unit tests with hand-calculated values

- [x] **1B.2 — EMAs (8, 20, 50) + EMA Fan**
  - EMA_8, EMA_20, EMA_50
  - EMA Fan boolean: `EMA_8 > EMA_20 > EMA_50`
  - Unit tests: each EMA + fan true/false cases

- [x] **1B.3 — SMAs (50, 200)**
  - SMA_50, SMA_200 (simple moving averages, NOT exponential)
  - Separate from EMAs — used by the Trend composite component
  - Unit tests: SMA_50 = mean of last 50 closes, verify exactly

- [x] **1B.4 — MACD Histogram**
  - EMA_12, EMA_26, Signal line (9-period EMA of MACD)
  - Histogram = MACD - Signal
  - Unit tests with known values

- [x] **1B.5 — ADX(14)**
  - +DI, -DI, DX, smoothed ADX (Wilder's smoothing)
  - Most complex indicator — test thoroughly
  - Unit tests with known values, edge case: flat price → ADX near 0

- [x] **1B.6 — ATR(14)**
  - True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
  - ATR = Wilder's smoothed average over 14 periods
  - Unit tests with hand-calculated values

- [x] **1B.7 — Wick Ratios + Distance from 20d Low**
  - Upper wick: `(High - max(Open, Close)) / (High - Low)`
  - Lower wick: `(min(Open, Close) - Low) / (High - Low)`
  - Edge case: `High == Low` → both = 0.0
  - Distance from 20d low: `(Close - min(Low, 20d)) / Close`
  - Unit tests including edge cases

- [x] **1B.8 — Relative Strength vs USD**
  - Rolling 20d z-score of `XAU_close / EURUSD_close` ratio
  - Requires EUR/USD data from storage
  - Unit tests with synthetic data

- [x] **1B.9 — Indicator assembly function**
  - `compute_all_indicators(ohlcv_df, eurusd_df) → DataFrame` with all 14 features
  - Wires 1B.1–1B.8 into a single function
  - Integration test: real data → no NaNs after warmup, all 14 columns present

- [x] **1B.10 — TradingView verification**
  - Script that prints RSI, EMA_8, SMA_200, ADX, ATR for 5 random dates
  - Side-by-side format for manual comparison against TradingView

#### Momentum Composite

- [x] **1B.11 — Rolling z-score utility**
  - `rolling_zscore(series, window=252) → Series`
  - All 5 components depend on this
  - Edge cases: insufficient history → NaN, zero std dev → NaN
  - Unit tests: known distributions, edge cases

- [x] **1B.12 — Momentum component (44%)**
  - `momentum_raw = close[t-21] / close[t-126] - 1`
  - Z-score via 1B.11
  - Unit tests: trending → positive, flat → near zero

- [x] **1B.13 — Trend component (22%)**
  - `trend_raw = (close > SMA_50) + (close > SMA_200) + (SMA_50 > SMA_200)` → 0 to 3
  - Z-score via 1B.11
  - Unit tests: golden cross + price above both → 3, death cross + below → 0

- [x] **1B.14 — RSI filter component (17%)**
  - `rsi_raw = 50 - abs(RSI_14 - 50)` → 0 to 50
  - Z-score via 1B.11
  - Unit tests: RSI=50 → max, RSI=80 → low

- [x] **1B.15 — ATR volatility component (11%)**
  - `atr_percentile = percentile_rank(ATR_14, 252d window)`
  - `atr_raw = 1 - abs(atr_percentile - 50) / 50` → 0.0 to 1.0
  - Z-score via 1B.11
  - Unit tests: median ATR → 1.0, extreme → near 0

- [x] **1B.16 — Support/Resistance proximity component (6%)**
  - `sr_raw = 1 - (high_20d - close) / close` Only upside proximity (long-only strategy). Proximity to 20d low is not rewarded.
  - Z-score via 1B.11
  - Unit tests: close at 20d high → 1.0, close 2% below → 0.98, close far below → lower

- [x] **1B.17 — Composite assembly + signal classification**
  - Weighted sum: `mom×0.44 + trend×0.22 + rsi×0.17 + atr×0.11 + sr×0.06`
  - Thresholds: STRONG_BUY >2.0σ, BUY >1.5σ, NEUTRAL, SELL <-1.5σ, STRONG_SELL <-2.0σ
  - Integration test: all components end-to-end with real data
  - Unit tests: threshold edge cases (exactly 1.5, exactly 2.0)

- [x] **1B.18 — Pullback threshold validation**
  - Plot histogram of `(Close - EMA_8) / EMA_8` across all historical gold data
  - Determine % of days within 2%. Output: histogram + summary stats.
  - Informs whether the 2% threshold in Guard 4 needs adjustment.

---

### Task 1C: Guard System

#### Infrastructure

- [x] **1C.1 — Guard ABC + GuardResult dataclass**
  - `guards/base.py`: abstract `Guard` with `evaluate()` method
  - `GuardResult` frozen dataclass: `passed`, `guard_name`, `reason`
  - Unit tests: construction, GUARDS_ENABLED toggle logic

- [x] **1C.2 — Guard pipeline runner**
  - `run_guards()`: iterates enabled guards, skips disabled, returns `List[GuardResult]`
  - Signal valid only if all enabled guards pass. Disabled → logged as SKIPPED.
  - Unit tests: all pass, one fails, disabled → skipped, all disabled → passes

#### Individual Guards

- [x] **1C.3 — Macro Gate**
  - EUR/USD close > EUR/USD 200 SMA → pass
  - 200 SMA calculated on EUR/USD data (not gold)
  - Unit tests: above → pass, below → fail, exactly at → edge case

- [x] **1C.4 — Trend Gate**
  - ADX(14) > 20 → pass
  - Unit tests: ADX=25 → pass, ADX=15 → fail, ADX=20 → fail (not > 20)

- [x] **1C.5 — Economic calendar JSON + generation script**
  - `data/calendars/economic_calendar.json` covering 2016–2027
  - Helper script to generate NFP dates (first Friday of each month)
  - FOMC/CPI from published schedules
  - Validation: no duplicates, valid dates, sorted

- [x] **1C.6 — Event Guard**
  - No FOMC/NFP/CPI within 2 calendar days in either direction → pass
  - 5-day window: 2 before + event day + 2 after
  - Unit tests: 3 before → pass, 2 before → fail, day of → fail, 2 after → fail, 3 after → pass
  - Test weekend handling

- [x] **1C.7 — Pullback Zone**
  - `(Close - EMA_8) / EMA_8 <= 0.02` → pass
  - Negative distance passes (intentional)
  - Unit tests: 1% → pass, 3% → fail, 2% → pass (<=), negative → pass

#### Portfolio Manager (dependency for Drawdown Gate and sizing)

- [x] **1C.8 — Portfolio Manager**
  - `portfolio/manager.py`: reads/writes portfolio state via StorageBackend
  - Tracks: cash, equity, positions, high_water_mark, drawdown_pct, throttle_state, closed_trades
  - Methods: `open_position()`, `close_position()`, `update_equity()`, `get_drawdown()`, `get_throttle_state()`, `resume_from_halted()`
  - Throttle state machine: NORMAL ↔ THROTTLED_50 ↔ THROTTLED_MAX1 ↔ HALTED with hysteresis
  - THROTTLED_MAX1 inherits halved sizing from THROTTLED_50 AND adds max-1-position cap
  - Recovery: 12% → THROTTLED_50 (not NORMAL), 8% → NORMAL only below 6%
  - `resume_from_halted()`: evaluates current DD → places in correct state (not blindly NORMAL)
  - Unit tests: open/close, drawdown calc, state transitions at 8%/12%/15%, recovery, THROTTLED_MAX1 halves AND caps, resume DD evaluation

- [x] **1C.9 — Drawdown Gate**
  - Drawdown < 15% → pass (HALTED → fail)
  - Only checks 15% halt. Throttling at 8%/12% is in sizing.
  - Unit tests: 0% → pass, 14.9% → pass, 15% → fail, 20% → fail

#### Integration

- [x] **1C.10 — Guard system integration test**
  - Synthetic data → indicators → all guards → pipeline result
  - Scenarios: all pass, single fail, multiple fail, disabled → skipped
  - Verify reason strings are informative

---

### Task 1D: Signal Generation

- [x] **1D.1 — Signal dataclass**
  - Frozen dataclass: date, asset, direction, composite_score, signal_strength, trap_order_stop, trap_order_limit, stop_loss, take_profit, trailing_stop_atr_mult, position_size, risk_amount, risk_reward_ratio, guards_passed, ttl
  - Unit tests: construction, field validation

- [x] **1D.2 — Trap Order calculation**
  - `buy_stop = signal_day_high + (0.02 × ATR_14)`
  - `limit = buy_stop + (0.05 × ATR_14)`
  - Uses signal day's candle and ATR
  - Unit tests: known candle + ATR → exact prices

- [x] **1D.3 — Stop loss + take profit**
  - SL: `entry - (2 × signal_day_ATR_14)` — fixed at entry
  - TP: `clamp(2 + signal_day_ADX/30, 2.5, 4.5) × signal_day_ATR_14` above entry — fixed at entry
  - Unit tests: low ADX → 2.5x, mid → scaled, high → 4.5x

- [x] **1D.4 — Position sizing (dual-constraint + throttle + cash reserve)**
  - ATR-based: `(equity × risk_pct) / (ATR_14 × 2)`
  - Cap-based: `(equity × 0.15) / entry_price`
  - `size = min(atr, cap)`. Apply throttle: halve if THROTTLED_50 or THROTTLED_MAX1. Check cash reserve. Round down to 0.01.
  - Unit tests: each tier, each constraint binding, throttle halving at both levels, cash reserve reduction

- [x] **1D.5 — Partial position rule**
  - If any position open (full or trailing 50%), block new signals
  - Unit tests: no position → allow, position open → block

- [x] **1D.6 — Signal generation pipeline**
  - Composite → threshold → guards → trap order → sizing → Signal object
  - Only BUY/STRONG_BUY proceed. Guard fail → no signal. Partial rule → no signal.
  - Unit tests: below threshold → no signal, guard fail → no signal, all pass → valid Signal

- [x] **1D.7 — Historical signal scan**
  - Run pipeline across full history, output all signals as parquet
  - Diagnostic tool for spot-checking, not the backtest
  - Verify no future data leakage

---

### Task 1E: Backtest Engine

#### Foundation

- [x] **1E.1 — Pseudocode first**
  - Write day-by-day loop in pseudocode before implementing
  - Cover: signal → trap order → fill → exits → costs → equity → drawdown → throttle

- [x] **1E.2 — Backtest dataclasses**
  - `Trade`: entry/exit dates, prices, direction, size, pnl, exit_reason, days_held, costs
  - `BacktestResult`: equity_curve (DataFrame), trade_log (list[Trade]), metrics (dict)
  - Unit tests: construction

- [x] **1E.3 — Account model**
  - €15,000 start, no additions. Track: cash, equity, high_water_mark, drawdown_pct, throttle_state
  - In-memory (reset per run, not persisted)
  - Unit tests: initial state, cash after open, equity with unrealized P&L

#### Execution Logic

- [x] **1E.4 — Trap Order fill logic**
  - `next_day_high >= buy_stop AND next_day_low <= limit` → filled at buy_stop
  - No fill → order expires. Gap-throughs rejected naturally by fill condition.
  - Unit tests: clean fill, high misses stop → no fill, low misses limit → no fill, gap-through → no fill

- [x] **1E.5 — Stop loss execution**
  - Day's low <= stop_loss → exit at stop_loss price
  - Applies to full position (pre-TP) or remaining 50% (post-TP)
  - Unit tests: SL hit day 1, day 5, never hit

- [x] **1E.6 — Take profit (50% close)**
  - Day's high >= take_profit → close 50% at TP price
  - Set `tp_50_hit = True`, remaining → trailing stop
  - Unit tests: TP hit → half closed, remaining size correct

- [x] **1E.7 — Trailing stop (after TP only)**
  - Only active when `tp_50_hit = True`
  - `trail = highest_high_since_entry - (2 × signal_day_ATR_14)`
  - Update daily at close. Ratchets up only.
  - Day's low <= trail → close remaining at trail price
  - Unit tests: ratchets up, stays flat on down days, exit when breached

- [x] **1E.8 — Time stop**
  - Close remaining at close price after 10 trading days (not calendar)
  - Unit tests: 10 days → closed, SL on day 7 → time stop not triggered

- [x] **1E.9 — Exit priority**
  - Same-day: SL > TP > trailing > time stop
  - SL + TP same candle → SL wins
  - Unit tests: SL+TP → SL wins, trail+time → trail wins

#### Cost Model

- [x] **1E.10 — Spread + slippage**
  - Spread: 0.3 pts/side. Slippage: 0.1 pts/side. Total round-trip: 0.8 pts.
  - Unit tests: costs deducted correctly

- [x] **1E.11 — IG overnight funding**
  - Formula: notional × (FEDFUNDS + 2.5%) / 365 per night. Uses FEDFUNDS forward-fill.
  - Unit tests: 1-night, 5-night, 10-night costs

#### Risk Management

- [x] **1E.12 — Drawdown throttling in backtest**
  - Full state machine: NORMAL → THROTTLED_50 (≥8%) → THROTTLED_MAX1 (≥12%) → HALTED (≥15%)
  - THROTTLED_MAX1 inherits halved sizing from THROTTLED_50 AND adds max-1-position
  - In backtest, HALTED → when DD drops below 8% → THROTTLED_50 (not NORMAL). Then DD < 6% → NORMAL.
  - Recovery hysteresis: 12% → THROTTLED_50, 8% → NORMAL only below 6%
  - Unit tests: size reduction at levels, THROTTLED_MAX1 halves AND caps, recovery through states, HALTED recovery to THROTTLED_50

#### Metrics & Output

- [x] **1E.13 — Performance metrics**
  - Sharpe (annualized, rf=FEDFUNDS), Sortino, profit factor, max DD (% and duration), win rate, total trades, avg win, avg loss, avg win/loss ratio, annualized return
  - Unit tests: hand-calculate for small trade log, verify

- [x] **1E.14 — Equity curve + trade log**
  - Daily equity DataFrame: date, equity, drawdown_pct, throttle_state
  - Trade log as tuple[Trade, ...] in BacktestResult
  - Unit tests: columns correct, P&L sums match equity changes

- [x] **1E.15 — Backtest report (Plotly HTML)**
  - Static HTML: equity curve, drawdown chart, monthly heatmap, trade log table, metrics summary
  - Plotly embedded, no server. Self-contained HTML string.

- [x] **1E.16 — Backtest integration test**
  - Full engine on synthetic data with known outcomes
  - Verify: fills, P&L, equity consistency
  - Edge cases: no signals, all signals, drawdown halt, TP+SL same candle

---

### Task 1F: Walk-Forward & Validation

- [x] **1F.1 — Walk-forward framework**
  - Expanding: 3yr train, 6mo test, 6mo roll. Fixed params.
  - Output: per-window Sharpe (in-sample + OOS)
  - Unit tests: window slicing on synthetic data

- [x] **1F.2 — Walk-forward efficiency**
  - WFE = mean(OOS Sharpe) / mean(in-sample Sharpe). Pass >50%.
  - Unit tests: known Sharpes → verify

- [x] **1F.3 — Monte Carlo bootstrap**
  - 10,000 resamples. 5th percentile terminal equity > starting capital.
  - Unit tests: resampling, percentile

- [x] **1F.4 — Shuffled-price test**
  - Permute daily returns, re-run 1,000+ times. Real Sharpe > 99th pctile (p < 0.01).
  - Unit tests: shuffling preserves distribution, destroys sequence

- [x] **1F.5 — t-statistic**
  - `t = mean_return × √N / std_return > 2.0`
  - Unit tests: known returns → verify

- [x] **1F.6 — Composite threshold sensitivity**
  - 1.0σ to 2.5σ in 0.25σ steps → Sharpe, DD, trade count

- [x] **1F.7 — ATR multiplier sensitivity**
  - 1.5, 2.0, 2.5, 3.0 → Sharpe, DD, win rate

- [x] **1F.8 — TP multiplier sensitivity**
  - min 2.0–3.0, max 3.5–5.0 → Sharpe, profit factor

- [x] **1F.9 — Momentum lookback sensitivity**
  - 3M (63d), 6M (126d), 9M (189d), 12M (252d) → full backtest each

- [x] **1F.10 — EMA periods sensitivity**
  - 8/20/50, 10/21/55, 12/26/50 → full backtest each

- [x] **1F.11 — Fill price sensitivity**
  - Default: fill at buy_stop. Test: fill at buy_stop + 0.5 × (limit - buy_stop) (midpoint).
  - Strategy must still be profitable with adverse fill assumption.
  - If it breaks → edge is too thin, investigate.

- [x] **1F.12 — Guard ablation study**
  - Disable each guard individually. Compare Sharpe/DD/trades vs baseline.
  - If disabling improves or doesn't change → flag for removal.

- [x] **1F.13 — GO/NO-GO report**
  - Compile results. Check kill conditions. PASS/FAIL per criterion.

---

### Task 1G: Telegram Bot

Build only after 1F.13 = GO.

#### Message Formatting

- [ ] **1G.1 — Signal card formatter**
  - `Signal` → Telegram message with emoji (🟢📊🎯🛑✅)
  - Unit tests: known Signal → verify output

- [ ] **1G.2 — Daily briefing formatter**
  - Portfolio + market → briefing. Sections: portfolio, positions, risk, market, signals.
  - No-signal: "Cash is a position."
  - Unit tests: with position, empty, throttled

- [ ] **1G.3 — Heartbeat formatter**
  - `✓ ingest 2026-03-10 23:00 UTC — 0.4s — XAU composite: 1.2σ NEUTRAL`
  - Sent to `WEALTHOPS_TELEGRAM_HEARTBEAT_CHAT_ID`

#### Bot Commands

- [ ] **1G.4 — /status** — equity, P&L, drawdown, throttle state
- [ ] **1G.5 — /portfolio** — positions, entry, unrealized P&L, days held, cash, allocation %
- [ ] **1G.6 — /executed \<id\>** — confirm execution (optional price), opens position
- [ ] **1G.7 — /skip \<id\>** — skip signal, mark skipped
- [ ] **1G.8 — /close \<id\>** — close position (optional exit price), record trade
- [ ] **1G.9 — /risk** — drawdown %, throttle, heat, cash reserve %
- [ ] **1G.10 — /resume** — resume from HALTED. Evaluates current DD to determine correct state: DD ≥ 12% → THROTTLED_MAX1, DD ≥ 8% → THROTTLED_50, DD < 6% → NORMAL. Does NOT blindly reset to NORMAL.
- [ ] **1G.11 — /help** — list all commands

Unit tests for each: valid input, invalid input, edge cases.

#### Bot Infrastructure

- [ ] **1G.12 — Polling mode** — python-telegram-bot, handlers, error handling. Integration test.
- [ ] **1G.13 — Webhook mode** — stateless Lambda handler, same routing. Unit tests.
- [ ] **1G.14 — Proactive sending** — signal cards, briefings, heartbeats. Unit tests.

#### Orchestrator

- [ ] **1G.15 — runner.py**
  - `run_ingest()`: fetch → indicators → composite → guards → signal → Telegram → heartbeat
  - `run_briefing()`: portfolio + market → briefing → Telegram → heartbeat
  - Integration test: mock externals, verify flows

#### Integration

- [ ] **1G.16 — Bot integration test**
  - signal → card → /executed → updated → /status → /close → updated
  - Mocked Telegram + StorageBackend. State consistency.

---

### Task 1H: Packaging & Deployment

- [ ] **1H.1 — S3Storage** — behind `[aws]` extra. Same interface. Mock boto3. Graceful if missing.
- [ ] **1H.2 — CLI skeleton** — `wealthops`: ingest, briefing, bot, backtest, health
- [ ] **1H.3 — wealthops ingest** — calls `run_ingest()`, `--bootstrap` flag
- [ ] **1H.4 — wealthops briefing** — calls `run_briefing()`
- [ ] **1H.5 — wealthops bot** — polling or webhook mode
- [ ] **1H.6 — wealthops backtest** — runs engine, outputs report
- [ ] **1H.7 — wealthops health** — check heartbeat, exit 0/1, stale = >14h

- [ ] **1H.8 — pyproject.toml**
  - Deps: pandas, requests, fredapi, python-telegram-bot, python-dotenv, click/typer, plotly
  - Optional: `[aws]` with boto3. Scripts: `wealthops = "trading_advisor.cli:main"`. Python >=3.12.

- [ ] **1H.9 — Deploy configs** — crontab, systemd, Lambda handler, Dockerfile, EventBridge

- [ ] **1H.10 — Deploy to target** — install, env vars, bootstrap, cron + bot
- [ ] **1H.11 — Monitoring** — UptimeRobot or CloudWatch
- [ ] **1H.12 — Autonomous verification** — 3+ trading days, briefings, heartbeats, commands, state persists

---

## Success Criteria

- [ ] Backtest Sharpe > 0.5, max DD < 20% over 5+ years
- [ ] Walk-forward efficiency > 50%
- [ ] Monte Carlo 5th percentile positive
- [ ] Shuffled-price p < 0.01
- [ ] Parameter sensitivity: wide plateau
- [ ] Total trades > 100
- [ ] Telegram sends signals and briefings
- [ ] Portfolio tracks correctly via commands
- [ ] Bot runs on schedule
- [ ] All guards have unit tests
- [ ] Indicators verified against TradingView
