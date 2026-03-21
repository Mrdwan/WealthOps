# WealthOps — Progress Tracker


---

## Recent Activity

_Update this section after each work session. Keep the last 5-10 entries. Oldest entries can be archived or deleted._

| Date | What Happened |
|------|--------------|
| 2026-03-17 | Created CLAUDE.md routing document. Refined memory bank architecture: CLAUDE.md as entry point, phase1-plan.md trimmed to strategy-only, PROGRESS.md expanded with decisions log. Planning to use Notion for granular task tracking. |
| 2026-03-10 | Initial project planning complete. All four docs (phase1-plan, Architecture, CODING_STANDARDS, PROGRESS) drafted and reviewed. |

---

## Decisions Made

_Log significant decisions here with brief rationale so they don't get re-discussed._

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-10 | EUR/USD as inverted DXY proxy | Same Tiingo forex endpoint as gold. No extra data source needed. |
| 2026-03-10 | Guard toggle system with ablation study | GUARDS_ENABLED config dict. Data decides which guards stay, not assumptions. |
| 2026-03-10 | StorageBackend ABC with LocalStorage + S3Storage | Deployment-agnostic from day one. S3 behind optional `[aws]` extra. |
| 2026-03-10 | €15,000 starting capital | Comfortable headroom above IG minimums at 2% risk per trade. |
| 2026-03-10 | No vectorbt | Trap Order logic too custom. Write backtest loop with pandas. |
| 2026-03-10 | All config via WEALTHOPS_* env vars | No config files. python-dotenv for local, SSM/Lambda env for AWS. |

---

## Open Questions

_Things still being figured out. Remove once resolved and add to Decisions Made._

- **pandas-ta vs manual indicator implementation?** pandas-ta is convenient but may not match TradingView exactly for some indicators. Need to verify during Task 1B.
- **Click vs Typer for CLI?** Both work. Typer is newer and has auto-generated help. Pick during Task 1H.
- **Support/Resistance detection method?** "Price clustering" is vague. Need to define the exact algorithm during Task 1B. Options: pivot points, volume profile zones (no volume for gold though), or simple rolling min/max proximity.

---

## Task Checklist

_Canonical task status lives in Notion "WealthOps Tasks" database. This checklist is a fallback summary._

### Task 1A: Data Pipeline
- [ ] Tiingo API integration (XAU/USD daily OHLCV)
- [ ] EUR/USD daily data (Tiingo forex, for Macro Gate)
- [ ] FRED integration (VIX, T10Y2Y, FEDFUNDS)
- [ ] OHLCV validation rules (high >= low, no nulls, no gaps, etc.)
- [ ] Parquet storage with incremental updates
- [ ] Bootstrap script for historical data (5-10 years)
- [ ] Verify: row counts, date ranges, no gaps on trading days

### Task 1B: Indicators & Composite
- [ ] Technical indicators (RSI, EMAs, ADX, ATR, MACD, wick ratios)
- [ ] Momentum composite (5 components, z-scored rolling 252d, weighted)
- [ ] Signal classification (STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL)
- [ ] Verify: compare RSI, EMA, ADX against TradingView for 5 random dates

### Task 1C: Guard System
- [ ] Macro Gate (EUR/USD > 200 SMA)
- [ ] Trend Gate (ADX > 20)
- [ ] Event Guard (no FOMC/NFP/CPI within 2 days)
- [ ] Pullback Zone (close within 2% of EMA_8)
- [ ] Drawdown Gate (portfolio drawdown < 15%)
- [ ] Economic calendar JSON (manually maintained)
- [ ] Unit tests for each guard with known inputs

### Task 1D: Signal Generation
- [ ] Composite + guard pipeline integration
- [ ] Trap Order calculation (buy stop, limit, gap-through rejection)
- [ ] Position sizing (dual-constraint)
- [ ] Partial position rule (trailing 50% blocks new entries)
- [ ] Lookahead bias prevention (signals use prior day's close)
- [ ] Verify: manually check 5 signals against chart

### Task 1E: Backtest Engine
- [ ] Day-by-day execution loop (write pseudocode FIRST)
- [ ] Trap Order fill logic (high >= stop AND low <= limit)
- [ ] Gap-through rejection
- [ ] Stop loss, take profit (50% close), trailing stop (daily at close)
- [ ] Time stop (10 trading days)
- [ ] Cost model (IG spread 0.3pts, slippage 0.1pts, actual IG overnight funding formula)
- [ ] Drawdown throttling active during backtest
- [ ] Account model: €15,000 flat, no monthly additions
- [ ] Output: Sharpe, profit factor, max DD, win rate, trade count, equity curve, monthly heatmap, trade log

### Task 1F: Walk-Forward & Validation
- [ ] Walk-forward optimization (3yr expanding train, 6mo test, 6mo roll)
- [ ] Monte Carlo bootstrap (10,000 resamples, 5th percentile positive)
- [ ] Shuffled-price test (strategy fails on random data, p < 0.01)
- [ ] t-statistic > 2.0
- [ ] Parameter sensitivity heatmaps (composite thresholds, ATR mult, TP mult, lookback)
- [ ] Guard ablation study (toggle each guard off, compare vs baseline)
- [ ] GO/NO-GO decision

### Task 1G: Telegram Bot
- [ ] Signal card formatting
- [ ] Daily briefing formatting
- [ ] Commands: /status, /portfolio, /executed, /skip, /close, /risk, /help
- [ ] Portfolio state read/write via StorageBackend
- [ ] Polling mode (laptop/Pi)
- [ ] Webhook mode (Lambda)
- [ ] Heartbeat messages to monitoring channel
- [ ] Verify: send test signal, run all commands, check state updates

### Task 1H: Packaging & Deployment
- [ ] StorageBackend ABC + LocalStorage implementation
- [ ] S3Storage implementation (behind [aws] extra)
- [ ] CLI entry points: ingest, briefing, bot, backtest, health
- [ ] Config from WEALTHOPS_* env vars only
- [ ] pyproject.toml: package metadata, extras, scripts entry point
- [ ] deploy/ example configs (crontab, systemd, Lambda handler, EventBridge)
- [ ] PyPI publish
- [ ] Deploy to chosen target (laptop, Pi, or AWS)
- [ ] Cron/EventBridge scheduled (23:00 UTC ingest, 09:00 UTC briefing, Mon-Fri)
- [ ] Telegram bot running (polling or webhook)
- [ ] UptimeRobot or CloudWatch monitoring configured
- [ ] Verify: full cycle runs autonomously for 3+ days

---

## Kill Conditions (stop and reassess if any trigger)
- Backtest Sharpe < 0.3 after tuning
- Shuffled-price test passes (p > 0.05)
- Walk-forward efficiency < 30%
- Win rate > 75% (overfit)
- < 50 trades in 5 years
