# WealthOps — Phase 1 Plan (Strategy Specification)

> **Scope:** This document covers the *strategy* — what to trade, how to score it, when to enter/exit, and how to validate it. For system design, directory structure, deployment, and tech stack, see `Architecture.md`.

## What This Is

Phase 1 of a portfolio-aware trading advisory bot. We start with one asset, one signal type, and one question: does this have edge?

The end vision: a system that monitors multiple asset classes, understands your portfolio, and sends Telegram alerts with actionable recommendations. But Phase 1 is gold only.

---

## Why XAU/USD on IG First

1. **Tax-free profits.** Spread betting in Ireland is exempt from CGT and income tax. On stocks via IBKR you'd pay 33% on gains. On a €3,000 gold profit, that's €990 you keep instead of giving to Revenue.
2. **Gold trends well.** Macro-driven (rates, dollar strength, geopolitical risk) creating multi-week moves. Good for swing trading on daily candles.
3. **Daily candles fit your life.** Bot runs once at market close. Check Telegram in the morning. No watching 4H charts at 3am.
4. **IG has a REST API.** Pull account data programmatically for Phase 2.
5. **Minimum trade is 0.01 lots.** Start small while validating.

---

## Strategy: Momentum Composite + Hard Guards

Daily candles, 3-10 day hold period, long only.

### The Momentum Composite (Signal Generator)

Six components, z-score normalized (rolling 252 trading-day window), weighted:

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| Momentum (6M return, skip last month) | 40% | Core trend strength. Academic basis: Jegadeesh & Titman 1993 |
| Trend Confirmation (price vs 50/200 DMA) | 20% | Are moving averages aligned? |
| RSI Filter (RSI 14, distance from extremes) | 15% | Not overbought/oversold |
| Volume Confirmation (20d/50d volume ratio) | 10% | Institutional participation. **Skipped for XAU/USD** (no centralized volume). Weight redistributes to others. |
| ATR Volatility (normalized ATR percentile) | 10% | Prefer moderate volatility, avoid dead or chaotic markets |
| Support/Resistance (price clustering) | 5% | Near key levels |

```
composite = weighted sum of z-scores

STRONG_BUY  = composite > 2.0σ
BUY         = composite > 1.5σ
NEUTRAL     = between -1.5σ and 1.5σ
SELL        = composite < -1.5σ
```

For XAU/USD, volume is excluded. Weights redistribute proportionally:
Momentum 44%, Trend 22%, RSI 17%, ATR 11%, S/R 6%.

### The Hard Guards (Pass/Fail Gates)

Signal only fires if ALL applicable guards are green. Any red = stay cash.

| # | Guard | Rule | Why |
|---|-------|------|-----|
| 1 | **Macro Gate** | EUR/USD > 200 SMA (weak dollar = strong euro = gold bullish) | Gold moves inversely to dollar strength. EUR/USD is an inverted DXY proxy (57.6% of DXY weight), available on Tiingo. |
| 2 | **Trend Gate** | ADX(14) > 20 | Don't trade ranging markets |
| 3 | **Macro Event Guard** | No FOMC/NFP/CPI within 2 days | These events whipsaw gold violently |
| 4 | **Pullback Zone** | (Close - EMA_8) / EMA_8 <= 0.02 | Don't chase extended moves. 2% filters out genuinely extended entries. Validate threshold against historical distance-from-EMA_8 distribution in Task 1B. |
| 5 | **Drawdown Gate** | Portfolio drawdown < 15% | See Dynamic Drawdown Throttling below |

Guards 2 (Panic/VIX) and 5 (Event/Earnings) from Wealth-Ops v3 don't apply to gold. They activate when stocks are added in Phase 2.

### Entry: The Trap Order

Don't market-buy at close. Place a conditional order:

- **Buy Stop:** High of signal candle + (0.02 × ATR_14)
- **Limit:** Stop price + (0.05 × ATR_14)
- **If price gaps through the limit → order doesn't fill.** By design. Gap-throughs are unreliable breakouts.
- **TTL:** Expires at next 23:00 UTC data ingest (~24h for IG gold).

This filters out false breakouts. You only enter if price confirms the move next session.

### Exit Rules

- **Stop Loss:** Entry - (2 × ATR_14). Placed as broker order on IG (executes in real-time, no bot needed).
- **Take Profit:** ADX-scaled target = clamp(2 + ADX/30, 2.5, 4.5) × ATR_14. Close 50% at TP.
- **Trailing Stop:** Chandelier at Highest_High - (2 × ATR_14). Updated once daily at market close for the remaining 50%. You manually adjust the IG stop order each morning. Backtest simulates this same once-daily-at-close logic.
- **Time Stop:** Close after 10 trading days if neither TP nor SL hit.
- **Partial Position Rule:** While trailing the remaining 50%, no new entry signals are taken. The trailing position counts as an open position and blocks new entries until it closes.

### Position Sizing

Dual-constraint (whichever is smaller):

```
ATR-based:  (Portfolio × risk_pct) / (ATR_14 × 2)
Cap-based:  Portfolio × 0.15 / Entry_Price

Position = min(ATR_based, Cap_based)
```

Risk percentage scales with capital:

| Capital | Risk/Trade | Max Positions | Portfolio Heat | Cash Reserve |
|---------|-----------|--------------|----------------|--------------|
| < €5,000 | 1.0% | 3 | 6% | 40% minimum |
| €5,000-€15,000 | 1.5% | 4 | 8% | 30% minimum |
| ≥ €15,000 | 2.0% | 5 | 10% | 25% minimum |

Phase 1 only trades gold, so max positions = 1. The table matters in Phase 2+. With €15,000 starting capital, you begin in the top tier (2% risk, €300 per trade).

### Dynamic Drawdown Throttling

| Drawdown | Action |
|----------|--------|
| 0-8% | Normal operations |
| 8-12% | Cut position sizes by 50%. Telegram alert. |
| 12-15% | Max 1 position. Close weakest. Daily alerts. |
| > 15% | HALT ALL TRADING. Manual review required. |

Recovery thresholds: 8% resumes at <6%, 12% resumes at <8%, 15% requires manual resume.

---

## Phase 1 Build Order

### Task 1A: Data Pipeline (Week 1)

**Goal:** Fetch XAU/USD daily OHLCV and store locally.

**Data source:** Tiingo Forex API (free tier, 50 requests/hour, tier-1 bank pricing).

**What to fetch:**
- XAU/USD daily OHLCV (minimum 5 years, ideally 10)
- EUR/USD daily (for Macro Gate, inverted DXY proxy). Same Tiingo forex endpoint.
- VIX daily from FRED (for future use and regime context)
- FRED macro data: T10Y2Y (yield curve), FEDFUNDS

**Validation rules (enforce on every ingest):**
- high >= low
- high >= open AND high >= close
- low <= open AND low <= close
- No null values in OHLCV
- Timestamps monotonically increasing
- No duplicate timestamps
- Price within 5% of previous close (flag anomalies)

**Deliverable:** Python script that fetches, validates, saves to parquet, and incrementally updates.

**Test:** Row counts, date ranges, no gaps on trading days.

### Task 1B: Indicator & Composite Calculation (Week 1-2)

**Goal:** Calculate all features and the momentum composite score for each day.

**Feature vector for XAU/USD (12 features, no volume):**

| # | Feature | Formula |
|---|---------|---------|
| 1 | RSI(14) | Standard Wilder RSI |
| 2 | EMA_8 | Exponential Moving Average, 8-period |
| 3 | EMA_20 | Exponential Moving Average, 20-period |
| 4 | EMA_50 | Exponential Moving Average, 50-period |
| 5 | MACD Histogram | EMA_12 - EMA_26 - Signal_9 |
| 6 | ADX(14) | Average Directional Index |
| 7 | ATR(14) | Average True Range |
| 8 | Upper Wick Ratio | (High - max(Open,Close)) / (High - Low) |
| 9 | Lower Wick Ratio | (min(Open,Close) - Low) / (High - Low) |
| 10 | EMA Fan | Boolean: EMA_8 > EMA_20 > EMA_50 |
| 11 | Distance from 20d Low | (Close - min(Low, 20d)) / Close |
| 12 | Relative Strength vs USD | Rolling 20d z-score of XAU/EUR-USD ratio |

**Momentum composite (5 components, volume excluded, all z-scored over rolling 252 trading-day window):**
- Momentum: 6-month return, skip most recent month. z-scored. Weight: 44%
- Trend: relationship between close, 50 DMA, 200 DMA. z-scored. Weight: 22%
- RSI: distance from extremes (penalize >70, <30). z-scored. Weight: 17%
- ATR volatility: percentile rank of current ATR. z-scored. Weight: 11%
- Support/Resistance: price clustering detection. z-scored. Weight: 6%

**Edge case handling:**
- (High - Low) == 0 → both wick ratios = 0.0
- RS ratio normalized to rolling 20d z-score

**Deliverable:** Function that takes OHLCV DataFrame, returns DataFrame with all features + composite score + signal classification.

**Test:** Compare RSI, EMA, ADX values against TradingView for 5 random dates. Should match within rounding error.

### Task 1C: Guard System (Week 2)

**Goal:** Implement the 5 hard guards as a pass/fail pipeline.

Each guard is a pure function: takes current market data, returns True (pass) or False (fail) with a reason string.

```python
@dataclass(frozen=True)
class GuardResult:
    passed: bool
    guard_name: str
    reason: str

GUARDS_ENABLED = {
    "macro_gate": True,
    "trend_gate": True,
    "event_guard": True,
    "pullback_zone": True,
    "drawdown_gate": True,  # should always stay on
}

def run_guards(market_data, portfolio_state, enabled=GUARDS_ENABLED) -> list[GuardResult]:
    """Runs only enabled guards. Signal valid if all enabled guards pass.
    Disabled guards are skipped and logged as 'SKIPPED' in results."""
```

**Economic calendar:** Hardcode known FOMC/NFP/CPI dates for the backtest period. In production, manually maintained JSON updated every 3-6 months.

**Test:** Unit test each guard with known inputs. EUR/USD at 1.05 with 200 SMA at 1.08 → macro gate fails. ADX at 18 → trend gate fails. 1 day before FOMC → event guard fails.

### Task 1D: Signal Generation (Week 2-3)

**Goal:** Combine composite score with guard pipeline to produce actionable signals.

For each day:
1. Calculate momentum composite → get signal classification
2. If BUY or STRONG_BUY → run through guard pipeline
3. If all guards pass → generate signal with Trap Order parameters
4. Calculate position size using dual-constraint formula

**Signal output structure:**
```python
@dataclass(frozen=True)
class Signal:
    date: datetime
    asset: str                    # "XAU/USD"
    direction: str                # "LONG"
    composite_score: float        # e.g., 1.87σ
    signal_strength: str          # "BUY" or "STRONG_BUY"
    trap_order_stop: float        # entry trigger price
    trap_order_limit: float       # max fill price
    stop_loss: float
    take_profit: float
    trailing_stop_atr_mult: float # 2.0
    position_size: float          # in lots
    risk_amount: float            # € at risk
    risk_reward_ratio: float
    guards_passed: list[GuardResult]
    ttl: str                      # "Expires 23:00 UTC"
```

**Critical: lookahead bias prevention.** All indicator values used for today's signal must be calculated using data available at yesterday's close. You never use today's close to decide today's action.

**Test:** Manually verify 5 signals against the chart. Does the entry make sense? Did price reach the trap order level the next day?

### Task 1E: Backtest Engine (Week 3-4)

**Goal:** Simulate trading every signal through history with realistic execution.

**Execution model:**
- Signal fires at EOD (23:00 UTC)
- Trap order placed for next session
- Fill condition: next day's high >= trap stop AND next day's low <= trap limit → filled at trap stop price
- Gap-through: next day's high > trap limit → NOT filled, signal expires
- Stop loss, take profit, trailing stop evaluated daily at close
- Time stop at 10 trading days

**Costs to model:**
- IG spread: ~0.3 points on XAU/USD per side
- IG overnight funding: Use IG's actual published formula (benchmark rate + IG markup, typically 2.5% annualized). This is ~0.01-0.02% per night for longs, compounds materially over 3-10 day holds across hundreds of trades.
- Slippage: 0.1 points per side

**Account model:**
- Starting capital: €15,000
- Monthly addition: None. Backtest must prove edge without cash injections.
- Tax rate: 0% (IG spread betting)
- Profits reinvested
- Drawdown throttling active during backtest (part of the strategy, not bolted on later)

**Output metrics:**

| Metric | Minimum | Overfitting Red Flag |
|--------|---------|---------------------|
| Sharpe Ratio | > 0.5 | > 3.0 |
| Profit Factor | > 1.2 | > 2.5 |
| Max Drawdown | < 20% | < 5% |
| Win Rate | > 35% | > 75% |
| Total Trades | > 100 | — |

Plus: annualized return, Sortino ratio, avg win/loss ratio, max DD duration, equity curve, monthly heatmap, full trade log.

### Task 1F: Walk-Forward + Statistical Validation (Week 4)

**Walk-forward optimization:**
```
Training window: 3 years (expanding)
Test window: 6 months
Roll forward: 6 months
Minimum periods: 10+ (5+ years of data)
```

**Statistical tests:**

| Test | Method | Pass Criteria |
|------|--------|--------------|
| Walk-Forward Efficiency | In-sample vs out-of-sample ratio | > 50% |
| Monte Carlo Bootstrap | 10,000 resamples of trade returns | 5th percentile still positive |
| Shuffled-Price Test | Permute daily returns, re-run strategy | Strategy fails on shuffled data (p < 0.01) |
| t-statistic | mean_return × √N / std_return | > 2.0 |

The shuffled-price test is the most important. If your strategy makes money on randomized price data, it has no real edge.

**Parameter sensitivity:**
- Composite thresholds: 1.0σ to 2.5σ in 0.25 increments
- ATR stop multiplier: 1.5, 2.0, 2.5, 3.0
- Take profit multiplier: 2.0 to 5.0
- Momentum lookback: 3M, 6M, 9M, 12M
- EMA periods: common combinations

Look for a wide plateau of profitability. Sharp peaks = overfit.

**Guard ablation study:** Toggle each guard off individually (via GUARDS_ENABLED). Compare Sharpe, max DD, and trade count against all-guards-on baseline. If disabling a guard improves or doesn't change performance, drop it. Macro Gate is the most likely candidate since gold sometimes rallies during dollar strength (safe haven flows). Let the data decide.

**Go/no-go gate:** Pass → proceed to 1G. Fail → iterate or try a different approach. Don't build infrastructure on a losing signal.

### Task 1G: Telegram Bot (Week 5)

**Goal:** Wire up Telegram to send signal cards and daily briefings.

Only build this AFTER the backtest validates.

**Signal card format:**
```
🟢 TRADE SIGNAL — LONG XAU/USD

📊 Composite: 1.87σ (BUY)
🎯 Trap Order: Buy Stop $2,352 | Limit $2,354
🛑 Stop Loss: $2,310 (-1.8%)
✅ TP: $2,410 (+2.5%) — Close 50%
📐 Trail: Chandelier at HH - (2 × ATR)

💰 Size: 0.02 lots (€30 risk = 1.0%)
⚖️ R:R: 2.5:1
🏷️ Broker: IG (spread bet — TAX FREE)

📈 Guards Passed:
  EUR/USD > 200 SMA (weak dollar) ✅
  ADX: 28 (trending) ✅
  No FOMC within 2 days ✅
  Pullback zone: 1.2% from EMA_8 ✅
  Drawdown: 0% ✅

⏰ Trap Order valid: ~24h (expires 23:00 UTC)
```

**Daily briefing format:**
```
📊 Daily Briefing — Feb 15, 2026

💰 Portfolio: €3,180 (+6.0%)
   Cash: €2,280 (71.7%)
   Positions: €900 (28.3%)

📈 Open Positions:
   XAU/USD LONG (IG)  +€60 (+6.7%) 🟢

🌡️ Risk Health:
   Portfolio Heat: 1.0% / 6% ✅
   Drawdown: 0.0% ✅
   Cash Reserve: 71.7% / 40% ✅

🔮 Market Context:
   EUR/USD: 1.092 (above 200 SMA — weak dollar) ✅
   Gold composite: 0.8σ (NEUTRAL)
   Next FOMC: 12 days

📋 No new signals today. Cash is a position.
```

**Telegram commands:**

| Command | Action |
|---------|--------|
| `/status` | Portfolio summary |
| `/portfolio` | Detailed position breakdown |
| `/executed <id>` | Confirm you executed a trade (optionally with price) |
| `/skip <id>` | Skip a signal |
| `/close <id>` | Mark position as closed (optionally with exit price) |
| `/risk` | Current risk parameters and drawdown |
| `/help` | List commands |

**Test:** Send test signal card. Run all commands. Verify portfolio state updates correctly.

### Task 1H: Packaging & Deployment (Week 5-6)

**Goal:** Bot runs daily, automatically, on your chosen platform.

See `Architecture.md` for full deployment details (directory structure, env vars, systemd config, Lambda setup, monitoring).

**Deliverable:** Bot running on chosen platform. Daily briefing at 9am, signal cards when they fire. Verify: runs autonomously for 3+ days.

---

## Phase 1 Success Criteria

- [ ] Backtest Sharpe > 0.5 and max drawdown < 20% over 5+ years
- [ ] Walk-forward efficiency > 50%
- [ ] Monte Carlo 5th percentile still positive
- [ ] Shuffled-price test: strategy fails on random data (p < 0.01)
- [ ] Parameter sensitivity shows wide profitable plateau
- [ ] Total trades > 100 in backtest period
- [ ] Telegram bot sends signal cards and daily briefings
- [ ] Portfolio state tracks correctly via Telegram commands
- [ ] Bot runs daily on schedule
- [ ] All guard logic has unit tests
- [ ] Indicator calculations verified against TradingView

## Phase 1 Kill Conditions

| Condition | Action |
|-----------|--------|
| Backtest Sharpe < 0.3 after parameter tuning | Strategy lacks edge on gold. Try stocks or different approach. |
| Shuffled-price test passes (p > 0.05) | Signal is noise, not edge. Redesign composite. |
| Walk-forward efficiency < 30% | Overfit. Simplify the model. |
| Win rate > 75% in backtest | Almost certainly overfit. Investigate. |
| < 50 trades in 5 years | Not enough data. Consider shorter timeframe or different asset. |

## What Phase 1 Does NOT Include

- No XGBoost or ML (Phase 3)
- No LLM sentiment analysis (Phase 4)
- No multi-asset support (Phase 2)
- No broker API integration (advisory only, manual execution on IG)
- No auto-execution
- No database (JSON via StorageBackend is enough)

## Future Phases (Summary)

**Phase 2:** US stocks via IBKR (33% CGT). Portfolio-aware sizing with correlation controls. VIX guard + earnings guard activate.
**Phase 3:** XGBoost second opinion. Regime classifier (LightGBM). Deploy only if backtest improves over baseline.
**Phase 4:** LLM rare opportunity detector. Sentiment scraping. Separate notification channel.
**Phase 5:** 3+ months paper trading. Minimum 20 trades. Results within 1σ of backtest.
**Phase 6:** Real capital. €15,000 start. Add capital only if tracking expectations after 3+ months.
