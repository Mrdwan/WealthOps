# WealthOps Phase 1 — Complete Teaching Guide
> For someone new to trading who wants to understand *why* everything exists, not just what to code.

---

## Table of Contents
1. [The Big Picture — What Are We Building?](#1-the-big-picture)
2. [Trading Basics You Must Know First](#2-trading-basics)
3. [Why Gold (XAU/USD) and Why IG?](#3-why-gold)
4. [Reading a Candle — OHLCV Explained](#4-reading-a-candle)
5. [The Momentum Composite — Your "Is It a Good Time to Buy?" Score](#5-momentum-composite)
6. [Each Indicator Explained Simply](#6-indicators)
7. [The Hard Guards — Your Safety Checklist](#7-hard-guards)
8. [Entry: The Trap Order](#8-trap-order)
9. [Exit Rules — When Do You Get Out?](#9-exit-rules)
10. [Position Sizing — How Much Do You Bet?](#10-position-sizing)
11. [Risk Management — The Drawdown System](#11-risk-management)
12. [Backtesting — Did This Work in the Past?](#12-backtesting)
13. [Statistical Validation — Is the Edge Real?](#13-statistical-validation)
14. [The Full System Flow — How Everything Connects](#14-system-flow)
15. [The Build Order — Why Tasks Are in This Sequence](#15-build-order)
16. [Glossary](#16-glossary)

---

## 1. The Big Picture

**What the system does in one sentence:**
Every evening, the bot looks at gold prices, runs a checklist, and if conditions are right, sends you a Telegram message saying "here's where to enter, where to put your stop loss, and how much to risk."

You then go to IG (a broker), place the trade manually. The bot doesn't trade for you — it *advises* you. Think of it as a very systematic analyst that never sleeps and has no emotions.

**The 3-layer decision:**
```
Layer 1: Is gold in a good momentum state right now?  → Momentum Composite (score)
Layer 2: Are all safety conditions met?               → Hard Guards (pass/fail)
Layer 3: If yes to both → send a specific trade plan  → Signal Card
```

That's the whole strategy. Everything else is infrastructure to make it reliable, automated, and testable.

---

## 2. Trading Basics

### What is "going long"?
You **buy** something hoping it goes up. You profit if price rises. You lose if price falls.

This system is **long only** — it only looks for buying opportunities. It never bets that gold will fall (no shorting in Phase 1).

### What is a Stop Loss?
A pre-set price where you automatically exit the trade if it goes against you. It's your "I was wrong, get me out" price.

Example: You buy gold at $2,350. Stop loss at $2,310. If gold drops to $2,310, you exit automatically. You lost $40 per unit. Without a stop loss, you'd just hold and hope — which destroys accounts.

### What is a Take Profit?
A pre-set price where you exit if the trade goes in your favour. Lock in the gain.

Example: Buy at $2,350, TP at $2,410. If gold reaches $2,410, you sell half. You made $60 on that half.

### What is Risk:Reward Ratio (R:R)?
How much you could make vs how much you could lose.

- Risk: distance from entry to stop loss
- Reward: distance from entry to take profit
- 2.5:1 R:R means: you risk €30 to potentially make €75

A system can be profitable even with a 40% win rate if the average win is 2.5× the average loss. This is why R:R matters more than win rate.

### What is a "position" / "lot"?
A position is an open trade. A lot is a unit of trade size. In gold spread betting:
- 1 lot = 100 oz of gold
- 0.01 lots = 1 oz of gold
- On IG, you can start tiny (0.01 lots)

### What is "swing trading"?
Holding trades for 3–10 days, not seconds (day trading) or months (investing). You catch a "swing" in one direction. The plan targets 3–10 day holds on daily candles.

### What is "spread betting" and why is it tax-free in Ireland?
Spread betting is a derivative product — you're not buying actual gold, you're betting on price movement. Irish Revenue Commissioners classify spread betting winnings as gambling winnings (not capital gains), so they're exempt from CGT (33%) and income tax. This is the biggest structural edge in the plan.

---

## 3. Why Gold (XAU/USD) and Why IG?

**XAU/USD** = the price of 1 troy ounce of gold in US dollars. The ticker XAU is gold, USD is the dollar.

**Why gold for Phase 1:**
- It trends for weeks to months (driven by interest rates, dollar strength, geopolitics)
- Trending markets are easier to trade than choppy ones
- Daily candles are enough — you don't need to watch charts all day
- No earnings surprises like stocks
- No need to analyse 500 companies

**Why IG specifically:**
- They support spread betting (tax-free)
- They have a REST API (you'll need this in Phase 2)
- They allow very small position sizes (0.01 lots = low risk while learning)
- They're a regulated, reputable broker in Ireland/UK

---

## 4. Reading a Candle — OHLCV

Every day of price data is summarised as one candlestick with 5 numbers:

```
O = Open  → price at start of day
H = High  → highest price during the day
L = Low   → lowest price during the day
C = Close → price at end of day
V = Volume → how many units were traded (not used for gold — no central exchange)
```

A **bullish candle** = Close > Open (price went up today). Usually shown in green.
A **bearish candle** = Close < Open (price went down today). Usually shown in red.

**Wicks** (the thin lines above/below the candle body):
- Upper wick = price went up to H but couldn't hold there, came back down
- Lower wick = price went down to L but buyers pushed it back up

Long lower wicks on bullish candles = buyers are in control. The plan calculates wick ratios as features.

---

## 5. The Momentum Composite — Your "Is It a Good Time to Buy?" Score

The composite is a single number that summarises 5 different signals into one score. Think of it as a judge with 5 expert witnesses — each gives an opinion, but some witnesses are more trusted (higher weight).

**Why composite instead of one indicator?**
Any single indicator fails a lot. RSI alone gives false signals constantly. By combining 5 different measures — each measuring a different *aspect* of market strength — you filter noise. If 4 out of 5 signals agree, you have higher confidence.

**The scoring process:**

Step 1: Calculate each component's raw value (e.g., RSI = 58)

Step 2: **Z-score normalize** it — this converts any number into "how many standard deviations above/below average is this?"
```
z = (value - rolling_mean) / rolling_std
```
A z-score of +2.0 means this reading is 2 standard deviations above the historical average — unusually strong. A z-score of -1.0 means slightly below average.

Step 3: Multiply each z-score by its weight and sum them:
```
composite = (momentum_z × 0.44) + (trend_z × 0.22) + (rsi_z × 0.17) + (atr_z × 0.11) + (sr_z × 0.06)
```

Step 4: Read the signal:
```
composite > 2.0σ  → STRONG BUY
composite > 1.5σ  → BUY
-1.5σ to 1.5σ    → NEUTRAL (do nothing)
composite < -1.5σ → SELL signal (ignored in Phase 1 — long only)
```

**Why 1.5σ as the threshold?**
In a normal distribution, ~87% of all values fall within ±1.5 standard deviations. So a composite above 1.5σ means gold is in unusually strong momentum — better than 87% of historical days. You only trade the unusual strong days.

---

## 6. Each Indicator Explained Simply

### 6.1 Momentum (6M return, skip last month) — Weight: 44%

**What it is:** How much has gold's price changed over the last 6 months? But we skip the most recent month.

**Why skip last month?** Academic research (Jegadeesh & Titman, 1993) showed that stocks that performed well over the last 6-12 months tend to continue performing well — but the very last month shows "reversal" (short-term mean reversion). Skipping it improves the signal.

**Formula:**
```
momentum = (Close[today - 22 days] / Close[today - 126 days]) - 1
```
(126 trading days ≈ 6 months, 22 days ≈ 1 month)

**Interpretation:** If gold is up 8% over the past 6 months (excluding last month), that's a strong upward trend. The system bets it continues.

### 6.2 Trend Confirmation (price vs 50/200 DMA) — Weight: 22%

**What is a Moving Average?**
The average closing price over the last N days. As each new day comes in, the oldest day drops off. It "moves" with time.

- **50 DMA** = average price over last 50 trading days (~2.5 months)
- **200 DMA** = average price over last 200 trading days (~10 months)

**What it measures:** Is gold above both its medium-term and long-term averages? If yes, the trend is up.

**The ideal state:**
```
Close > 50 DMA > 200 DMA → price above both averages, shorter average above longer average → confirmed uptrend
```

This is called "the golden cross alignment" when all three line up.

**Why include it?** Momentum can spike briefly. But if the 200 DMA is declining, it might just be a bounce in a downtrend. This component confirms the trend is structural, not just a blip.

### 6.3 RSI Filter — Weight: 17%

**What is RSI?**
Relative Strength Index. A number between 0 and 100.
- Above 70 = "overbought" (price rose too fast, due for a pullback)
- Below 30 = "oversold" (price fell too fast, due for a bounce)
- 30–70 = normal range

**What it measures here:** How close is RSI to the extremes? The system *penalizes* extreme RSI readings. It wants RSI in the healthy zone, not screaming overbought.

**Why?** If RSI is 78, gold is already extended. Chasing it now means buying near a local top — poor risk/reward. If RSI is 55, there's still room to run.

**The RSI calculation (Wilder's method):**
```
Average Gain = average of up-days' gains over 14 days
Average Loss = average of down-days' losses over 14 days
RS = Average Gain / Average Loss
RSI = 100 - (100 / (1 + RS))
```

### 6.4 ATR Volatility — Weight: 11%

**What is ATR?**
Average True Range. The average daily price range over 14 days. Measures how much gold moves day-to-day.

**True Range** for one day:
```
TR = max(High - Low, |High - PreviousClose|, |Low - PreviousClose|)
```
The vertical bars mean "absolute value." This handles gap opens (when today's open is far from yesterday's close).

**ATR = average of TR over 14 days.**

**What this component measures:** The percentile rank of current ATR. Where does today's ATR rank vs the last year?
- Very low ATR (bottom 20%) = market is "dead" — not moving enough to trade
- Very high ATR (top 20%) = too chaotic, hard to set stops reliably
- Middle range (40th–70th percentile) = ideal — enough movement to profit, controlled enough to manage risk

The component rewards moderate volatility and penalises both extremes.

### 6.5 Support/Resistance — Weight: 6%

**What is Support/Resistance?**
Price levels where the market has historically bounced or stalled.
- **Support:** A price floor. Gold has bounced up from $2,300 multiple times → $2,300 is a support level
- **Resistance:** A price ceiling. Gold has been rejected from $2,400 repeatedly → $2,400 is resistance

**How the plan calculates it:**
Price clustering — look at all the local highs and lows over the past year. Cluster them (they're rarely exact, usually within a small range). Where are the densest clusters? Those are your S/R zones.

**What the component does:** Is current price near a known support level? Buying near support = better entry. Buying near resistance = bad entry (you might immediately get rejected).

This component gets the lowest weight (6%) because S/R detection from code is imprecise. The other components are more reliable.

---

## 7. The Hard Guards — Your Safety Checklist

Even if the composite score is screaming BUY, the guards can veto the trade. **All 5 must pass.** One failure = no trade.

Think of it like a pre-flight checklist for a plane. Even if everything looks good, if one instrument is red, you don't fly.

### Guard 1: Macro Gate — Is the Dollar Weak?

**Rule:** DXY < 200 SMA

**What is DXY?**
The US Dollar Index. A measure of the dollar's strength against a basket of 6 other currencies (euro, yen, pound, etc.)

**Why does this matter for gold?**
Gold is priced in dollars. When the dollar strengthens, gold gets more expensive for foreign buyers → demand drops → gold price falls. When the dollar weakens, gold becomes cheaper internationally → demand rises → gold price rises.

They move **inversely**. Historically, ~80% of the time, dollar weakness coincides with gold strength.

**The rule in plain English:**
"Is the dollar currently below its average price over the last 200 trading days?" If yes, the dollar is in a downtrend — good for gold. If no (dollar is strong), don't trade gold long.

**DXY proxy:** Since the plan uses Tiingo, it uses UUP ETF or DX-Y.NYB as a proxy for DXY. They track the same thing.

### Guard 2: Trend Gate — Is Gold Actually Trending?

**Rule:** ADX(14) > 20

**What is ADX?**
Average Directional Index. Measures trend *strength* (not direction). Ranges from 0 to 100.
- ADX < 20 = no trend (market is ranging, choppy sideways movement)
- ADX 20–40 = developing trend
- ADX > 40 = strong trend
- ADX > 60 = very strong trend (uncommon)

**Why this matters:**
The momentum composite says "gold has been going up." But ADX tells you if it's going up *in an orderly, sustained way* or just bouncing randomly. Choppy markets eat your stop losses for breakfast — you get stopped out 3 times and then the market finally goes your direction without you.

**The rule in plain English:** "Is gold actually trending?" If ADX is 15, it's just noise. If ADX is 28, there's a real trend happening.

### Guard 3: Macro Event Guard — No Big News in 2 Days?

**Rule:** No FOMC, NFP, or CPI announcements within 2 days

**What are these events?**
- **FOMC** = Federal Open Market Committee. The US Federal Reserve's meeting where they decide interest rates. Gold moves violently on these — sometimes $50–$100 in minutes.
- **NFP** = Non-Farm Payrolls. Monthly US jobs report. Affects the dollar, which affects gold.
- **CPI** = Consumer Price Index. Monthly US inflation report. High inflation → gold demand rises. Low inflation → gold demand falls.

**Why 2 days, not same day?**
Markets often pre-position before major events (guessing the outcome). The 2-day buffer avoids both pre-event volatility AND the event itself.

**Why this matters:**
Even if your signal is perfect, a surprise FOMC statement can gap gold $80 against you in seconds, blowing through your stop loss entirely. This guard protects against known unknowable events.

### Guard 4: Pullback Zone — Are You Chasing?

**Rule:** (Close - EMA_8) / EMA_8 <= 0.05

**What is EMA?**
Exponential Moving Average. Like a regular moving average, but more recent prices get heavier weighting. EMA_8 is the 8-period EMA — it reacts quickly to recent price changes.

**What this measures:**
How far is current price above the 8-day EMA? If it's more than 5% above it, the move is "extended" — you'd be buying at the top of a run.

**In plain English:** "Did I miss the train?" If gold is 7% above its recent average price, the move is already extended. You're late. Waiting for a pullback is smarter.

**Why this is important:**
Extended entries have bad risk/reward. Your stop loss needs to be far away (because the move was big), but your upside is limited (because much of the move already happened). This guard ensures you enter when there's still room to run.

### Guard 5: Drawdown Gate — Is My Account Healthy?

**Rule:** Portfolio drawdown < 15%

**What is drawdown?**
The percentage drop from your account's peak value to its current value.

Example: Account peaked at €3,000. Now it's at €2,500. Drawdown = (3000-2500)/3000 = 16.7%.

**Why this matters:**
If you're on a losing streak, the worst thing you can do is keep taking full-size trades. You're compounding losses. This guard forces you to stop at 15% drawdown — which triggers a mandatory manual review. Maybe the market regime changed. Maybe a parameter needs adjustment.

The drawdown throttling (8%, 12%) kicks in before you hit this hard stop — cutting position sizes gradually.

---

## 8. Entry: The Trap Order

This is one of the most clever parts of the plan. Instead of buying immediately when the signal fires, you place a **conditional order** that only fills if price confirms the move.

### How it works

Signal fires at 23:00 UTC (market close). You don't buy at that closing price.

Instead, you instruct the broker:
```
Buy Stop Price  = Yesterday's High + (0.02 × ATR_14)
Limit Price     = Buy Stop Price  + (0.05 × ATR_14)
```

**Buy Stop:** "Don't buy unless price rises to this level." You only enter if tomorrow's session actually breaks above yesterday's high (plus a small buffer). This confirms the upward move is real.

**Limit Price:** "Don't buy if price is higher than this." If price **gaps through** your limit (opens above it), the order doesn't fill. Gap-throughs indicate unreliable breakouts — price moved too fast, often due to news.

**Example with real numbers:**
- Yesterday's High: $2,350
- ATR_14: $20
- Buy Stop: $2,350 + (0.02 × $20) = $2,350.40
- Limit: $2,350.40 + (0.05 × $20) = $2,351.40

If tomorrow, price rises to $2,350.40 but doesn't gap above $2,351.40 → you fill at $2,350.40. ✅  
If tomorrow opens at $2,355 (gap up, above the limit) → order doesn't fill. ✅ (Avoided a bad entry)  
If tomorrow never reaches $2,350.40 → order expires at 23:00 UTC the next day. ✅

### Why is this smart?

**Filters false breakouts.** Sometimes the composite says BUY but the next day price falls immediately — the signal was wrong. The trap order requires price to *prove* the signal by actually breaking higher. You only enter confirmed moves.

**Controls entry price.** You know your maximum entry price in advance. This makes your stop loss distance and position size calculable before the trade opens.

---

## 9. Exit Rules

You have 4 ways to exit a trade. The first one to trigger wins.

### Exit 1: Stop Loss (hard floor)
```
Stop Loss = Entry Price - (2 × ATR_14)
```
If price falls 2 ATRs below your entry, you exit. This is placed as a **broker order on IG** the moment you enter — so it executes even if your bot is offline, even at 3am.

Using ATR (not a fixed dollar amount) means the stop loss scales with how volatile gold currently is. In a volatile period, a $30 stop might be too tight (stopped out by noise). In a quiet period, $30 is plenty of buffer. ATR automatically adjusts.

### Exit 2: Take Profit (close 50% of position)
```
TP distance = clamp(2 + ADX/30, 2.5, 4.5) × ATR_14
```
The take profit scales with ADX. Why? Strong trends (high ADX) tend to run further. Weak trends should be taken off sooner.
- ADX = 20 → multiplier = clamp(2 + 20/30, 2.5, 4.5) = clamp(2.67, 2.5, 4.5) = 2.67× ATR
- ADX = 40 → multiplier = clamp(2 + 40/30, 2.5, 4.5) = clamp(3.33, 2.5, 4.5) = 3.33× ATR
- ADX = 70 → multiplier = clamp(2 + 70/30, 2.5, 4.5) = clamp(4.33, 2.5, 4.5) = 4.33× ATR

When TP hits, you close **50% of the position**. You pocket half the profit and let the other half ride.

### Exit 3: Trailing Stop (for the remaining 50%)
The Chandelier Exit:
```
Trailing Stop = Highest High since entry - (2 × ATR_14)
```
This trail ratchets *upward* as gold makes new highs. It never moves down. As gold climbs, so does your trailing stop — locking in more profit. When gold finally pulls back enough to hit the trailing stop, you exit the remaining 50%.

**Example:**
- Entry: $2,350
- 5 days later, gold's highest high = $2,420
- ATR = $20
- Trailing stop = $2,420 - (2 × $20) = $2,380 (above your entry — you're guaranteed profit on this half)

### Exit 4: Time Stop
If after 10 trading days you're still in the trade (TP not hit, SL not hit, trailing stop not hit) → just exit. 

**Why?** A trade that doesn't move is a waste of capital. It could be tied up for weeks going sideways when there might be a better opportunity. The time stop forces you to re-evaluate and free up capital.

---

## 10. Position Sizing

**The question:** Given my account size and the risk of this specific trade, how many units should I buy?

**Dual constraint approach — take whichever is smaller:**

### ATR-Based Sizing (risk-driven)
```
ATR_size = (Portfolio × risk_pct) / (ATR_14 × 2)
```

**Where:**
- `risk_pct` = how much of your account you're willing to lose on this trade (1.0%, 1.5%, or 2.0% depending on account size)
- `ATR_14 × 2` = your stop loss distance in price terms

**Example:**
- Portfolio = €3,000
- Risk % = 1.0% → risk €30 per trade
- ATR_14 = $18 → stop loss distance = $36
- ATR_size = 30 / 36 = 0.83 oz

**Intuition:** You're saying "I want to lose at most €30 if stopped out." The ATR tells you how far away your stop is. Dividing risk by stop distance gives you the size.

### Cap-Based Sizing (exposure cap)
```
Cap_size = Portfolio × 0.15 / Entry_Price
```

Caps your total exposure to 15% of portfolio regardless of anything else. Prevents over-leveraging in volatile conditions.

**Example:**
- Portfolio = €3,000
- Entry price = $2,350
- Cap_size = (3,000 × 0.15) / 2,350 = €450 / $2,350 ≈ 0.19 oz

→ Take `min(0.83, 0.19)` = 0.19 oz. The cap wins.

**Why dual constraint?** ATR sizing could allow large positions in calm markets. The cap protects against over-exposure even when ATR says you can size up.

---

## 11. Risk Management — The Drawdown System

This is how the system behaves when you're losing.

### Portfolio Heat
Total risk currently deployed across all open positions. For Phase 1 (gold only, 1 position max), this is just the risk on your one gold trade.

Maximum heat allowed: 6% of portfolio (for accounts under €5,000). This means all your open stop losses combined can't exceed 6% of your total account.

### Cash Reserve
Minimum cash you must maintain. For small accounts: 40%. This prevents you from being fully deployed when a big opportunity arrives.

### The Throttle System

| Drawdown | Action |
|----------|--------|
| 0–8% | Trade normally |
| 8–12% | Cut position sizes in half. Get a Telegram alert. |
| 12–15% | Max 1 position. Close your weakest trade. Daily alerts. |
| > 15% | **STOP ALL TRADING.** Manual review required. |

**Why this is crucial:**
When you're on a losing streak, your account is smaller, so fixed-size losses represent larger percentages. Cutting size during drawdown breaks this compounding cycle. You lose less during bad periods and preserve capital to recover when things improve.

**Recovery thresholds** (to prevent yo-yo behaviour):
- Throttle activated at 8% → resumes normal only when drawdown is back under 6%
- Throttle activated at 12% → resumes only when back under 8%
- 15% halt → requires you to manually restart (by design)

---

## 12. Backtesting

**The fundamental question:** "Would this strategy have made money historically?"

You take 5–10 years of gold price data and *simulate* running the strategy as if you didn't know the future. You calculate the composite score, run the guards, generate signals, simulate the trap orders, exits, and position sizing — and track the result.

### Why backtesting matters
Before you risk real money, you need evidence the strategy has edge. Backtesting isn't perfect (past doesn't guarantee future), but it can tell you:
- Does this signal have any pattern?
- Are the exit rules sensible?
- How deep do losses get during bad periods?

### The execution model
The plan simulates realistic execution:
- Signal fires at 23:00 UTC (end of day)
- Next day: if the day's price range includes the trap order stop price AND doesn't gap above the limit → fill at stop price
- If gap-through → no fill
- Evaluate SL, TP, trailing stop daily
- Include real costs: IG spread (~0.3 pts), overnight funding (~0.008%/night), slippage (0.1 pts)

**Lookahead bias prevention:** This is critical. When generating a signal for Day N, you can only use data from Day N-1 and earlier. You never peek at what Day N's close was before deciding. This is an easy way to accidentally "cheat" in backtests — and it's why real results often disappoint.

### Key metrics explained

**Sharpe Ratio:** (Return - Risk-free rate) / Volatility. Above 0.5 = acceptable. Above 1.0 = good. Above 3.0 = probably overfit.

**Profit Factor:** Total gross profit / Total gross loss. 1.5 means for every €1 you lost, you made €1.50 elsewhere.

**Max Drawdown:** Largest peak-to-trough drop during the backtest period. < 20% is the target. This is what keeps you from quitting when things go bad.

**Win Rate:** % of trades that were profitable. 35%+ is the target. Sounds low, but with 2.5:1 R:R, even 40% wins is profitable.

**Total Trades > 100:** Statistical requirement. Fewer trades = results could be luck. With 100+ trades over 5 years, you have meaningful evidence.

---

## 13. Statistical Validation — Is the Edge Real?

Good backtests aren't enough. Markets are complex, and it's easy to accidentally fit a model to past noise. These tests check if the edge is genuine.

### Walk-Forward Testing
Instead of testing the strategy on *all* the data you used to build it (in-sample), you repeatedly:
1. Train/tune parameters on 3 years of data
2. Test on the next 6 months (out-of-sample, data the strategy never "saw")
3. Roll forward 6 months and repeat

**Walk-Forward Efficiency = Out-of-sample performance / In-sample performance**

If in-sample Sharpe is 1.5 and out-of-sample is 0.8, efficiency = 53%. Above 50% = acceptable. If efficiency is 10%, the strategy just memorised the training data.

### Monte Carlo Bootstrap
Take all 100+ historical trades and their individual returns. Randomly reshuffle the order 10,000 times, each time calculating what the equity curve would look like.

**The 5th percentile:** Even in the unluckiest 5% of scenarios (most losses clustered at the start), is the strategy still profitable? If yes, the edge is robust to bad luck sequences.

### Shuffled-Price Test (Most Important)
Take the raw price data. Randomly shuffle the daily returns (destroying any real patterns). Re-run the complete strategy on this scrambled data.

**If the strategy still makes money on random price data → you have no real edge.** You curve-fit to noise.

**Pass criteria:** The strategy should *fail* on shuffled data (p < 0.01). This proves the strategy relies on real patterns in gold's price behaviour, not accidental overfitting.

### t-Statistic
```
t = mean_return × √N / std_return
```
Tests if the average trade return is statistically different from zero. Above 2.0 means you can say with 95% confidence the edge is real, not luck.

### Parameter Sensitivity
Test the strategy across a range of parameter values. For example, test the composite threshold from 1.0σ to 2.5σ.

- **Good:** Strategy is profitable across a wide plateau. Whether threshold is 1.4σ, 1.5σ, or 1.6σ, results are similar.
- **Bad (overfit):** Strategy is only profitable at exactly 1.5σ. Any other value tanks performance. This means you got lucky finding 1.5σ on historical data — it won't hold in live trading.

---

## 14. The Full System Flow

Here's how everything connects, from raw data to your Telegram message:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DAILY PIPELINE (23:00 UTC)                    │
└─────────────────────────────────────────────────────────────────┘

[Tiingo API]          [FRED API]           [Economic Calendar]
      │                    │                       │
      ▼                    ▼                       ▼
 XAU/USD OHLCV        DXY, VIX          FOMC/NFP/CPI dates
 (daily candles)   yield curve data
      │                    │
      └──────────────┬─────┘
                     │
                     ▼
              [Data Storage]
             Parquet files on S3
                     │
                     ▼
         ┌───────────────────────┐
         │   Indicator Engine     │
         │ RSI, EMA, ADX, ATR,   │
         │ MACD, wick ratios...  │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Momentum Composite   │
         │  Z-score 5 components │
         │  → NEUTRAL/BUY/       │
         │    STRONG_BUY signal  │
         └───────────┬───────────┘
                     │
              BUY or STRONG_BUY?
                     │
                    YES
                     │
                     ▼
         ┌───────────────────────┐
         │     Guard Pipeline     │
         │  1. Macro Gate (DXY)  │
         │  2. Trend Gate (ADX)  │
         │  3. Event Guard       │
         │  4. Pullback Zone     │
         │  5. Drawdown Gate     │
         └───────────┬───────────┘
                     │
             All 5 guards pass?
                     │
                    YES
                     │
                     ▼
         ┌───────────────────────┐
         │    Signal Generator    │
         │  Trap order prices    │
         │  Stop loss price      │
         │  Take profit price    │
         │  Position size        │
         │  R:R ratio            │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │    Telegram Bot        │
         │  Sends signal card    │
         │  to your phone        │
         └───────────────────────┘
                     │
                     ▼
              👤 YOU (Mohamed)
         Checks Telegram at 9am,
         manually places trade on IG
```

**Daily briefing at 09:00 UTC** runs the same pipeline but just reports portfolio status + market context, even if no signal fired.

---

## 15. The Build Order — Why Tasks Are in This Sequence

The plan builds from the bottom up. Each task produces something testable before you move on.

```
Task 1A: Data Pipeline
├── Reason: Nothing works without data. This is the foundation.
├── What you prove: Data comes in clean, consistent, complete.
└── Output: Parquet files with 5+ years of XAU/USD, DXY, VIX

Task 1B: Indicator & Composite Calculation
├── Reason: Signals need indicators. Indicators need data.
├── What you prove: RSI, EMA, ADX, ATR match TradingView (ground truth)
└── Output: DataFrame with all features + composite score per day

Task 1C: Guard System
├── Reason: Need guards before generating signals (signals need guards to validate)
├── What you prove: Each guard passes/fails correctly with known inputs
└── Output: Guard pipeline that returns pass/fail + reason for each

Task 1D: Signal Generation
├── Reason: Combine composite + guards → actual signals
├── What you prove: Signals look correct on historical charts
└── Output: List of historical signals with all trade parameters

Task 1E: Backtest Engine
├── Reason: Are these signals profitable? You can't know without simulation.
├── What you prove: Sharpe > 0.5, drawdown < 20%, win rate > 35%
└── Output: Full backtest metrics, equity curve, trade log

Task 1F: Statistical Validation
├── Reason: Is the backtest edge real or curve-fit? CRITICAL GATE.
├── What you prove: Strategy has real edge (passes walk-forward, shuffled-price)
└── Output: Go/No-go decision. If no-go, fix strategy before building more.

Task 1G: Telegram Bot
├── Reason: Only build notification infrastructure AFTER validating the signal.
│          Building a beautiful bot for a losing strategy is wasted effort.
├── What you prove: Bot receives commands, sends signals, tracks portfolio state
└── Output: Working Telegram bot

Task 1H: Deployment
├── Reason: Now that everything works locally, make it run automatically forever.
├── What you prove: Lambda executes daily, bot runs without your intervention
└── Output: Fully automated system on AWS
```

**The golden rule:** Don't build infrastructure on top of an unvalidated signal. Task 1F is the gatekeeper — if you fail there, go back and fix the strategy, not continue building.

---

## 16. Glossary

| Term | Plain English Definition |
|------|--------------------------|
| XAU/USD | Price of gold in US dollars |
| OHLCV | Open, High, Low, Close, Volume — the 5 data points of a candle |
| Spread betting | Betting on price direction without owning the asset. Tax-free in Ireland. |
| Long | Betting price goes up |
| Short | Betting price goes down (not used in Phase 1) |
| Stop Loss | Pre-set exit price if trade goes against you |
| Take Profit | Pre-set exit price when trade goes in your favour |
| Trailing Stop | A stop loss that moves up as price rises, locking in profit |
| ATR | Average True Range — daily volatility measurement |
| EMA | Exponential Moving Average — recent prices weighted more heavily |
| DMA | Days Moving Average (50 DMA, 200 DMA) |
| RSI | Relative Strength Index — momentum oscillator (0-100) |
| ADX | Average Directional Index — trend strength (not direction) |
| DXY | US Dollar Index — measures dollar strength |
| FOMC | Federal Reserve interest rate decision meetings |
| NFP | US Non-Farm Payrolls — monthly jobs report |
| CPI | Consumer Price Index — inflation measurement |
| Z-score | How many standard deviations above/below average a value is |
| Sharpe Ratio | Risk-adjusted return. Higher = better return for risk taken |
| Drawdown | % drop from account peak to current value |
| Position sizing | Calculating how many units to buy based on risk parameters |
| Lot | Standard unit of trade size. 1 lot = 100 oz of gold |
| Lookahead bias | Accidentally using future data to make past decisions in backtests. Cheating. |
| Walk-forward | Testing strategy on data it never saw during parameter tuning |
| Overfitting | Strategy works perfectly on past data but fails in live trading |
| Lambda | AWS serverless computing — runs your code on a schedule without a server |
| Parquet | Columnar file format optimised for financial timeseries data |
| CGT | Capital Gains Tax — 33% in Ireland (avoided via spread betting) |
| R:R | Risk:Reward ratio |
| Portfolio heat | Total % of portfolio currently at risk across all open positions |
| Chandelier Exit | A trailing stop calculated as Highest High minus ATR multiple |

---

## Where to Go From Here

**Week 1 starting point — Task 1A:**

1. Sign up for a free Tiingo account (tiingo.com) — get your API key
2. Sign up for FRED API (fred.stlouisfed.org) — free, instant
3. Create your project structure (clone the folder layout from the plan)
4. Write the data fetcher for XAU/USD daily data
5. Run the validation rules on every row
6. Save to parquet, verify row counts and date ranges

The very first thing you write should be a Python function that returns 5 years of clean gold price data. Everything else builds on that.

**Good resources to build conceptual understanding alongside coding:**
- Investopedia for any financial term you don't understand
- TradingView (free) — visualise every indicator you implement. Use it as ground truth to verify your calculations.
- The original momentum paper: "Returns to Buying Winners and Selling Losers" (Jegadeesh & Titman, 1993) — 5 pages, readable, explains why momentum works.
