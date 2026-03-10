# WealthOps Trading Advisor — Merged Phase 1 Plan

## What This Is

Phase 1 of a portfolio-aware trading advisory bot. We're combining the domain knowledge from (tax strategy, risk management, guard system, momentum composite) with an incremental build approach where every step is independently testable.

The end vision hasn't changed: a system that monitors multiple asset classes, understands your portfolio, and sends you Telegram alerts with actionable recommendations. But we start with one asset, one signal type, and one question: does this have edge?

---

## Why XAU/USD on IG First

Not BTC. Not stocks. Gold on IG spread betting.

1. **Tax-free profits.** Spread betting in Ireland is exempt from CGT and income tax. On stocks via IBKR you'd pay 33% on gains. On a €3,000 gold profit, that's €990 you keep instead of giving to Revenue. Tax alpha is the easiest edge you'll ever find.
2. **Gold trends well.** It's driven by macro factors (rates, dollar strength, geopolitical risk) that create multi-week moves. Perfect for swing trading on daily candles.
3. **Daily candles fit your life.** Bot runs once at market close. You check Telegram in the morning. No watching 4H charts at 3am.
4. **IG has a REST API.** You can pull account data and positions programmatically for Phase 2.
5. **Minimum trade is 0.01 lots.** You can start small while validating.

---

## Strategy: Momentum Composite + Hard Guards

This is a "Swing Sniper" adapted for Phase 1. Daily candles, 3-10 day hold period, long only.

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
| 1 | **Macro Gate** | EUR/USD > 200 SMA (weak dollar = strong euro = gold bullish) | Gold moves inversely to dollar strength. We use EUR/USD (inverted DXY proxy, 57.6% of DXY weight) because actual DXY isn't available on Tiingo. |
| 2 | **Trend Gate** | ADX(14) > 20 | Don't trade ranging markets |
| 3 | **Macro Event Guard** | No FOMC/NFP/CPI within 2 days | These events whipsaw gold violently |
| 4 | **Pullback Zone** | (Close - EMA_8) / EMA_8 <= 0.02 | Don't chase extended moves. 5% is too loose for gold — it almost never triggers. 2% filters out genuinely extended entries. Validate this threshold against historical distance-from-EMA_8 distribution in Task 1B. |
| 5 | **Drawdown Gate** | Portfolio drawdown < 15% | See risk management section |

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

Phase 1 only trades gold, so max positions = 1. The table matters in Phase 2+. With €15,000 starting capital, you begin in the top tier (2% risk, €300 per trade), which gives comfortable headroom above IG's minimum position size on gold.

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
- EUR/USD daily (for Macro Gate, inverted DXY proxy). Same Tiingo forex endpoint as XAU/USD.
- VIX daily from FRED (for future use and regime context)
- FRED macro data: T10Y2Y (yield curve), FEDFUNDS

**Storage:** Local parquet files. No S3, no DynamoDB yet. Directory structure:

```
data/
├── ohlcv/
│   ├── XAUUSD_daily.parquet
│   ├── EURUSD_daily.parquet
│   └── SPY_daily.parquet
├── macro/
│   ├── VIX.parquet
│   ├── T10Y2Y.parquet
│   └── FEDFUNDS.parquet
└── calendars/
    └── economic_calendar.json    # FOMC/NFP/CPI dates
```

**Validation rules (enforce on every ingest):**
- high >= low
- high >= open AND high >= close
- low <= open AND low <= close
- No null values in OHLCV
- Timestamps monotonically increasing
- No duplicate timestamps
- Price within 5% of previous close (flag anomalies)

**Deliverable:** A Python script that fetches data, validates it, saves to parquet, and can incrementally update with new data.

**Test:** Run it. Check row counts, date ranges, no gaps on trading days.

### Task 1B: Indicator & Composite Calculation (Week 1-2)

**Goal:** Calculate all features and the momentum composite score for each day in the dataset.

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

**Deliverable:** Function that takes OHLCV dataframe, returns dataframe with all features + composite score + signal classification (STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL).

**Test:** Compare RSI, EMA, ADX values against TradingView for 5 random dates. They should match within rounding error.

### Task 1C: Guard System (Week 2)

**Goal:** Implement the 5 hard guards as a pass/fail pipeline.

Each guard is a pure function: takes current market data, returns True (pass) or False (fail) with a reason string.

```python
# Pseudocode
class GuardResult:
    passed: bool
    guard_name: str
    reason: str  # e.g., "DXY at 104.2, above 200 SMA (103.8)"

# Guard toggle config — each guard can be enabled/disabled.
# Used in backtesting to test every combination and measure which guards
# actually improve performance vs which ones just filter out valid trades.
# Drawdown gate should always stay on.
GUARDS_ENABLED = {
    "macro_gate": True,
    "trend_gate": True,
    "event_guard": True,
    "pullback_zone": True,
    "drawdown_gate": True,
}

def macro_gate(eurusd_data) -> GuardResult: ...
def trend_gate(adx_value) -> GuardResult: ...
def macro_event_guard(economic_calendar, today) -> GuardResult: ...
def pullback_zone(close, ema_8) -> GuardResult: ...
def drawdown_gate(portfolio_state) -> GuardResult: ...

def run_guards(market_data, portfolio_state, enabled=GUARDS_ENABLED) -> List[GuardResult]:
    """Runs only enabled guards. Signal valid if all enabled guards pass.
    Disabled guards are skipped and logged as 'SKIPPED' in results."""
```

**Economic calendar:** For Phase 1, hardcode known FOMC/NFP/CPI dates for the backtest period. In production, fetch from FRED + Finnhub.

**Deliverable:** Guard pipeline that returns a clear pass/fail with human-readable reasons for each guard.

**Test:** Unit test each guard with known inputs. Example: EUR/USD at 1.05 with 200 SMA at 1.08 → macro gate fails (euro below average = strong dollar). ADX at 18 → trend gate fails. 1 day before FOMC → macro event guard fails.

### Task 1D: Signal Generation (Week 2-3)

**Goal:** Combine the composite score with the guard pipeline to produce actionable signals.

For each day:
1. Calculate momentum composite → get signal classification
2. If BUY or STRONG_BUY → run through guard pipeline
3. If all guards pass → generate signal with Trap Order parameters
4. Calculate position size using dual-constraint formula

**Signal output structure:**
```python
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
    guards_passed: List[GuardResult]
    ttl: str                      # "Expires 23:00 UTC"
```

**Critical: lookahead bias prevention.** All indicator values used for today's signal must be calculated using data available at yesterday's close. The signal says "if price breaks above X tomorrow, enter." You never use today's close to decide today's action.

**Deliverable:** Signal generator that processes the full dataset and outputs a list of historical signals.

**Test:** Manually verify 5 signals against the chart. Does the entry make sense? Did price actually reach the trap order level the next day?

### Task 1E: Backtest Engine (Week 3-4)

**Goal:** Simulate trading every signal through history with realistic execution.

**Execution model:**
- Signal fires at EOD (23:00 UTC)
- Trap order placed for next session
- If next day's high >= trap order stop price AND next day's low <= trap order limit → filled at trap order stop price
- If next day's high > trap order limit (gap through) → NOT filled. Signal expires.
- Stop loss, take profit, trailing stop evaluated daily at close (broker handles intraday on IG, but we simulate on daily)
- Time stop at 10 trading days

**Costs to model:**
- IG spread: ~0.3 points on XAU/USD per side
- IG overnight funding: Use IG's actual published formula (benchmark rate + IG markup, typically 2.5% annualized). Do not estimate. Pull the current formula from IG's website and hardcode it. At current rate environments this is closer to 0.01-0.02% per night for longs, significantly higher than naive estimates. Over hundreds of trades with 3-10 day holds this compounds and materially affects P&L.
- Slippage: 0.1 points per side

**Account model:**
- Starting capital: €15,000
- Monthly addition: None. The backtest must prove the strategy has edge on its own without cash injections masking poor performance. Model contributions separately outside the backtest if you want to project real account growth.
- Tax rate: 0% (IG spread betting)
- Profits reinvested

**Drawdown throttling active during backtest.** If the account hits 8% drawdown, position sizes halve. This is part of the strategy, not something you add later.

**Output metrics:**

| Metric | Minimum | Overfitting Red Flag |
|--------|---------|---------------------|
| Sharpe Ratio | > 0.5 | > 3.0 |
| Profit Factor | > 1.2 | > 2.5 |
| Max Drawdown | < 20% | < 5% |
| Win Rate | > 35% | > 75% |
| Total Trades | > 100 | — |

Additional outputs:
- Annualized return (%)
- Sortino ratio
- Average win / average loss ratio
- Max drawdown duration
- Equity curve plot
- Monthly returns heatmap
- Trade log with every entry, exit, reason, and P&L

### Task 1F: Walk-Forward + Statistical Validation (Week 4)

**Walk-forward optimization:**
```
Training window: 3 years (expanding)
Test window: 6 months
Roll forward: 6 months
Minimum periods: 10+ (5+ years of data)
```

The strategy must work on out-of-sample data, not just the period it was tuned on.

**Statistical tests:**

| Test | Method | Pass Criteria |
|------|--------|--------------|
| Walk-Forward Efficiency | In-sample vs out-of-sample performance ratio | > 50% |
| Monte Carlo Bootstrap | 10,000 resamples of trade returns | 5th percentile still positive |
| Shuffled-Price Test | Permute daily returns, re-run strategy | Strategy fails on shuffled data (p < 0.01) |
| t-statistic | mean_return × √N / std_return | > 2.0 |

The shuffled-price test is the most important. If your strategy makes money on randomized price data, it has no real edge. It's just curve fitting.

**Parameter sensitivity:**
- Composite thresholds: test 1.0σ to 2.5σ in 0.25 increments
- ATR stop multiplier: test 1.5, 2.0, 2.5, 3.0
- Take profit multiplier: test 2.0 to 5.0
- Momentum lookback: test 3M, 6M, 9M, 12M
- EMA periods: test common combinations

**Guard ablation study:** Run the backtest with each guard individually toggled off (using GUARDS_ENABLED config). Compare Sharpe, max drawdown, and trade count against the all-guards-on baseline. If disabling a guard improves or doesn't change performance, that guard isn't earning its place. The Macro Gate (DXY/EUR-USD) is the most likely candidate to be dropped, since gold sometimes rallies during dollar strength (safe haven flows). Let the data decide.

Look for a wide plateau of profitability. Sharp peaks = overfit.

**Deliverable:** Backtest report with all metrics, equity curve, walk-forward results, Monte Carlo distribution, parameter heatmap.

**Go/no-go gate:** If the strategy passes statistical validation → proceed to Task 1G. If it fails → iterate on parameters or try a different approach. Do not build infrastructure on a losing signal.

### Task 1G: Telegram Bot (Week 5)

**Goal:** Wire up Telegram to send signal cards and daily briefings.

Only build this AFTER the backtest validates. No point having beautiful notifications for a losing strategy.

**Signal card format (from Wealth-Ops v3):**
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

**Daily briefing (even when no signal):**
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

**Telegram commands (Phase 1 subset):**

| Command | Action |
|---------|--------|
| `/status` | Portfolio summary |
| `/portfolio` | Detailed position breakdown |
| `/executed <id>` | Confirm you executed a trade (optionally with price) |
| `/skip <id>` | Skip a signal |
| `/close <id>` | Mark position as closed (optionally with exit price) |
| `/risk` | Current risk parameters and drawdown |
| `/help` | List commands |

Portfolio state is tracked via these commands. You tell the bot what you did, it updates its model of your portfolio. No broker API integration needed yet.

**Deliverable:** Working Telegram bot that receives commands and sends formatted messages.

**Test:** Send yourself a test signal card. Execute the commands. Verify portfolio state updates correctly.

### Task 1H: Deployment (Week 5-6)

**Goal:** Bot runs daily, automatically. Choose your deployment target.

The package is infrastructure-agnostic. You install it, set env vars, and schedule the CLI commands. Two reference deployments are documented:

**Option A: Laptop / Raspberry Pi**
- `pip install wealthops` (or `uv add wealthops`)
- `.env` file with `WEALTHOPS_STORAGE=local` and API keys
- cron (or Task Scheduler on Windows):
  - 23:00 UTC Mon-Fri: `wealthops ingest`
  - 09:00 UTC Mon-Fri: `wealthops briefing`
- systemd service (or screen/tmux): `wealthops bot` (polling mode)
- UptimeRobot pings `wealthops health` endpoint
- Cost: €0/month (Pi: ~€100 one-time for hardware)

**Option B: AWS**
- `pip install wealthops[aws]` in a Docker container → push to ECR
- Lambda function with handler calling `wealthops ingest` / `wealthops briefing`
- EventBridge Scheduler for cron triggers
- Lambda Function URL for Telegram webhook (`WEALTHOPS_TELEGRAM_MODE=webhook`)
- S3 for storage (`WEALTHOPS_STORAGE=s3`)
- SSM Parameter Store for secrets
- Cost: < $1/month

**Deliverable:** Bot running on your chosen platform. You receive a daily briefing at 9am and signal cards when they fire. Verify: runs autonomously for 3+ days.

---

## Project Structure

```
trading-advisor/
├── pyproject.toml                  # uv managed, PyPI package config
├── src/
│   └── trading_advisor/
│       ├── __init__.py
│       ├── config.py              # loads all config from env vars (WEALTHOPS_*)
│       ├── cli.py                 # CLI entry points: ingest, briefing, bot, backtest, health
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── base.py            # StorageBackend ABC (read/write parquet + JSON)
│       │   ├── local.py           # LocalStorage (default, files on disk)
│       │   └── s3.py              # S3Storage (optional, behind [aws] extra)
│       ├── data/
│       │   ├── __init__.py
│       │   ├── base.py            # abstract DataProvider
│       │   ├── tiingo.py          # Tiingo implementation
│       │   └── fred.py            # FRED macro data
│       ├── indicators/
│       │   ├── __init__.py
│       │   ├── technical.py       # RSI, EMA, ADX, ATR, etc.
│       │   └── composite.py       # Momentum Composite calculation
│       ├── guards/
│       │   ├── __init__.py
│       │   ├── base.py            # abstract Guard + GuardResult + GUARDS_ENABLED config
│       │   ├── macro_gate.py
│       │   ├── trend_gate.py
│       │   ├── event_guard.py
│       │   ├── pullback_zone.py
│       │   └── drawdown_gate.py
│       ├── strategy/
│       │   ├── __init__.py
│       │   ├── base.py            # abstract Strategy
│       │   ├── swing_sniper.py    # combines composite + guards + trap order
│       │   └── sizing.py          # dual-constraint position sizing
│       ├── portfolio/
│       │   ├── __init__.py
│       │   └── manager.py         # portfolio state, drawdown tracking
│       ├── notifications/
│       │   ├── __init__.py
│       │   └── telegram.py        # bot (polling + webhook), commands, formatting
│       ├── backtest/
│       │   ├── __init__.py
│       │   ├── engine.py          # execution simulation
│       │   ├── validation.py      # walk-forward, Monte Carlo, shuffled-price
│       │   └── report.py          # metrics + charts
│       └── runner.py              # orchestrator: fetch → analyze → notify
├── tests/
│   ├── test_indicators.py
│   ├── test_composite.py
│   ├── test_guards.py
│   ├── test_signals.py
│   ├── test_sizing.py
│   ├── test_storage.py
│   └── test_notifications.py
├── scripts/
│   ├── backtest_xauusd.py         # run full backtest
│   └── bootstrap_data.py          # initial data download
├── data/                           # local parquet cache (gitignored)
├── logs/                           # rotating logs (gitignored)
└── deploy/                         # example deployment configs (not part of package)
    ├── wealthops-bot.service       # systemd unit file (Pi/Linux)
    ├── crontab.example             # cron schedule example
    ├── lambda/                     # AWS Lambda handler + Dockerfile
    └── eventbridge.json            # EventBridge schedule config
```

**Key design choices:**
- **PyPI package.** `pip install wealthops` for local/Pi use, `pip install wealthops[aws]` for S3 backend. Strategy code ships as the package. Deployment configs are examples in the repo, not part of the package.
- **Storage abstraction.** `StorageBackend` ABC with `LocalStorage` (default) and `S3Storage` (optional). The strategy never knows where data lives.
- **CLI entry points.** `wealthops ingest`, `wealthops briefing`, `wealthops bot`, `wealthops backtest`, `wealthops health`. How you schedule them is your choice (cron, EventBridge, Task Scheduler, whatever).
- **Config via env vars only.** All config comes from `WEALTHOPS_*` environment variables. No config files to manage across environments. On a laptop/Pi, use a `.env` file. On AWS, use SSM or Lambda env vars.
- **Telegram bot supports polling and webhook.** Polling for laptop/Pi (long-running process). Webhook for Lambda (stateless). Same bot code, different transport. Controlled by `WEALTHOPS_TELEGRAM_MODE=polling|webhook`.
- Abstract base classes for DataProvider, Guard, Strategy. When Phase 2 adds IBKR stocks, you implement interfaces. No refactoring.
- Guards are individual modules with toggle config. Easy to test, easy to add, easy to disable.
- Portfolio manager is simple in Phase 1 (JSON state, Telegram commands). Upgrades to DynamoDB + broker API in Phase 2.
- Backtest engine is separate from live runner. Same strategy code, different execution paths.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.12+ | Language |
| uv | Package management + environment |
| pandas + pandas-ta | Data manipulation + indicators |
| Tiingo API | XAU/USD, EUR/USD (forex endpoint) |
| FRED API | VIX, yield curve, fed funds |
| vectorbt or custom | Backtesting (evaluate both, vectorbt may not handle Trap Orders well) |
| matplotlib + plotly | Charts and heatmaps |
| python-telegram-bot | Telegram integration (polling + webhook) |
| click or typer | CLI entry points |
| python-dotenv | Env var loading from .env |
| boto3 (optional) | S3 storage backend, behind `[aws]` extra |
| pytest | Testing |

**pyproject.toml extras:**
```toml
[project.optional-dependencies]
aws = ["boto3"]

[project.scripts]
wealthops = "trading_advisor.cli:main"
```

**Deployment is not part of the package.** Example configs for cron, systemd, Lambda, and EventBridge live in `deploy/` in the repo. Users schedule `wealthops ingest` and `wealthops briefing` however they want.

**Note on vectorbt:** The Trap Order execution logic (buy stop + limit, gap-through rejection, time stops) is complex enough that vectorbt might not handle it natively. You may need a custom backtest loop. That's fine. Write it yourself with pandas. Simpler to debug than fighting a framework's abstractions.

---

## Phase 1 Success Criteria

- [ ] Backtest shows Sharpe > 0.5 and max drawdown < 20% over 5+ years
- [ ] Walk-forward efficiency > 50%
- [ ] Monte Carlo 5th percentile still positive
- [ ] Shuffled-price test: strategy fails on random data (p < 0.01)
- [ ] Parameter sensitivity shows wide profitable plateau
- [ ] Total trades > 100 in backtest period
- [ ] Telegram bot sends signal cards and daily briefings
- [ ] Portfolio state tracks correctly via Telegram commands
- [ ] Bot runs daily on schedule (cron, EventBridge, or equivalent)
- [ ] All guard logic has unit tests
- [ ] Indicator calculations verified against TradingView

---

## Phase 1 Kill Conditions

| Condition | Action |
|-----------|--------|
| Backtest Sharpe < 0.3 after parameter tuning | Strategy lacks edge on gold. Try stocks or different approach. |
| Shuffled-price test passes (p > 0.05) | Signal is noise, not edge. Redesign composite. |
| Walk-forward efficiency < 30% | Overfit. Simplify the model. |
| Win rate > 75% in backtest | Almost certainly overfit. Investigate. |
| < 50 trades in 5 years | Not enough data. Consider shorter timeframe or different asset. |

---

## What Phase 1 Does NOT Include

- No XGBoost or ML (Phase 3)
- No LLM sentiment analysis (Phase 4)
- No multi-asset support (Phase 2, add stocks after gold validates)
- No broker API integration (advisory only, you execute manually on IG)
- No rare opportunity detection (separate module, later)
- No auto-execution
- No database (JSON file via StorageBackend is enough for one user)
- No Docker (unless deploying to AWS Lambda)

---

## What Comes After Phase 1

**Phase 2:** Add US stocks via IBKR (33% CGT). Implement portfolio-aware sizing with correlation controls. The guard system expands (VIX guard, earnings guard activate for stocks). Telegram gets `/portfolio` depth with multi-asset breakdown.

**Phase 3:** XGBoost scoring as a second opinion alongside the momentum composite. Regime classifier (LightGBM) to adjust position sizing and guard thresholds. Deploy only if backtest proves it improves over baseline.

**Phase 4:** LLM-powered rare opportunity detector. Sentiment scraping from Reddit, Twitter/X, news. Event-driven alerts for asymmetric bets. Separate notification channel, never auto-sized above 2.5% of portfolio.

**Phase 5:** 3+ months paper trading across all assets. Minimum 20 trades. Live results must be within 1σ of backtest.

**Phase 6:** Real capital. Start with €15,000. This is the minimum needed to comfortably stay within 2% risk-per-trade given IG's minimum position sizes on gold. Add capital only if tracking expectations after 3+ months.
