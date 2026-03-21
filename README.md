<div align="center">

# WealthOps

**A rules-based swing trading advisory system for gold.**

Signal generation · Risk management · Telegram alerts · Runs on a Raspberry Pi

[![CI](https://github.com/mrdwan/wealthops/actions/workflows/ci.yml/badge.svg)](https://github.com/mrdwan/wealthops/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/type%20checked-mypy--strict-blue.svg)](https://mypy-lang.org/)

</div>

---

WealthOps monitors XAU/USD daily candles, scores momentum through a multi-factor composite signal, applies five hard safety guards, and sends actionable trade signals via Telegram. It doesn't execute trades. You read the signal, you decide, you place the order on IG.

The system runs on a Raspberry Pi with two cron jobs: one at market close (23:00 UTC) to scan for signals, one in the morning (09:00 UTC) to send you a portfolio briefing. That's it. No dashboard, no web app, no cloud dependency. Just a Pi, a Telegram bot, and a disciplined strategy.

> **Status:** Phase 1 — in active development. Building the core signal pipeline and validating edge through backtesting before going live. See the [build roadmap](docs/strategy/phase1-plan.md).

---

## How It Works

```
23:00 UTC — market close

    Fetch XAU/USD daily candle (Tiingo)
    Fetch EUR/USD, VIX, yields (Tiingo + FRED)
                    │
                    ▼
    Calculate indicators (RSI, EMAs, ADX, ATR, MACD)
                    │
                    ▼
    Score momentum composite (5 factors, z-scored, weighted)
                    │
                    ▼  if BUY or STRONG_BUY
    Run guard pipeline (all 5 must pass)
    ├── Macro Gate     — EUR/USD above 200 SMA (weak dollar)
    ├── Trend Gate     — ADX > 20 (trending market)
    ├── Event Guard    — no FOMC/NFP/CPI within 2 days
    ├── Pullback Zone  — price within 2% of EMA_8
    └── Drawdown Gate  — portfolio drawdown < 15%
                    │
                    ▼  all guards pass
    Generate signal with Trap Order parameters
    Calculate position size (dual-constraint)
                    │
                    ▼
    Send Telegram signal card

09:00 UTC — your morning coffee

    Send daily briefing: portfolio, risk health, market context
```

## The Signal Card

When a trade fires, you get this on Telegram:

```
🟢 TRADE SIGNAL — LONG XAU/USD

📊 Composite: 1.87σ (BUY)
🎯 Trap Order: Buy Stop $2,352 | Limit $2,354
🛑 Stop Loss: $2,310 (-1.8%)
✅ TP: $2,410 (+2.5%) — Close 50%
📐 Trail: Chandelier at HH - (2 × ATR)

💰 Size: 0.02 lots (€30 risk = 1.0%)
⚖️ R:R: 2.5:1

📈 Guards: all 5 passed ✅
⏰ Expires: 23:00 UTC tomorrow
```

You read it. You decide. You place (or skip) the order on IG.

## Why Gold on IG

Spread betting on IG in Ireland is exempt from capital gains tax and income tax. On a €3,000 profit from stocks via IBKR, you'd pay €990 to Revenue. On the same profit through IG spread betting, you keep all of it. Gold trends well on daily candles, driven by macro factors that create multi-week moves. The minimum trade is 0.01 lots, so you can start small while validating.

## Risk Management

This isn't a "set and forget" system. Risk is managed at every layer:

**Position sizing** uses dual constraints — ATR-based risk and capital-based cap — taking whichever is smaller. With €15,000 starting capital, that's roughly €300 risk per trade (2%).

**Drawdown throttling** kicks in automatically: at 8% drawdown, position sizes halve. At 12%, max one position. At 15%, all trading halts until manual review.

**The Trap Order** is the entry mechanism. Instead of buying at close, the system places a conditional order: a buy stop above the signal candle's high. If price doesn't confirm the breakout next session, the order expires unfilled. Gap-throughs are rejected by design.

**50% partial close** at the take-profit target. The remaining 50% trails with a Chandelier stop (highest high minus 2× ATR), updated daily. No new entries while trailing a position.

---

## Setup

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- API keys: [Tiingo](https://www.tiingo.com/) (free), [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) (free)
- A [Telegram bot](https://core.telegram.org/bots#creating-a-new-bot)

### Install

```bash
git clone https://github.com/mrdwan/wealthops.git
cd wealthops
uv sync
```

### Configure

```bash
cp .env.example .env
# Edit .env with your API keys and Telegram credentials
```

### Run

```bash
# Bootstrap historical data (first time only)
uv run python scripts/bootstrap_data.py

# Run a backtest
wealthops backtest

# Manual signal scan
wealthops ingest

# Manual briefing
wealthops briefing

# Start the Telegram bot
wealthops bot
```

### Deploy on Raspberry Pi

Add two cron jobs and a systemd service for the Telegram bot:

```cron
0 23 * * 1-5  cd ~/wealthops && wealthops ingest 2>&1 | tee -a logs/cron.log
0  9 * * 1-5  cd ~/wealthops && wealthops briefing 2>&1 | tee -a logs/cron.log
```

See [docs/architecture.md](docs/architecture.md) for the full deployment guide, including systemd config, monitoring with UptimeRobot, and an optional AWS Lambda setup.

---

## Telegram Commands

| Command | What it does |
|---------|-------------|
| `/status` | Portfolio summary |
| `/portfolio` | Detailed position breakdown |
| `/executed <id>` | Confirm you placed a trade |
| `/skip <id>` | Skip a signal |
| `/close <id>` | Mark a position closed |
| `/risk` | Current drawdown and risk parameters |
| `/help` | List commands |

---

## Tech Stack

| | |
|---|---|
| **Language** | Python 3.12+ |
| **Package manager** | uv |
| **Data** | pandas, pandera |
| **Indicators** | pandas-ta |
| **Market data** | Tiingo API (forex endpoint) |
| **Macro data** | FRED API (VIX, yields, fed funds) |
| **Messaging** | python-telegram-bot |
| **Quality** | ruff, mypy --strict, pytest (100% branch coverage) |
| **Deployment** | Raspberry Pi + cron (primary), AWS Lambda (optional) |

---

## Project Structure

```
wealthops/
├── src/trading_advisor/
│   ├── config.py              # env var loading, storage backend init
│   ├── cli.py                 # entry points: ingest, briefing, bot, backtest, health
│   ├── storage/               # StorageBackend ABC + LocalStorage + S3Storage
│   ├── data/                  # Tiingo + FRED data providers
│   ├── indicators/            # RSI, EMA, ADX, ATR, MACD, composite
│   ├── guards/                # 5 hard gates, individually toggleable
│   ├── strategy/              # signal generation, position sizing
│   ├── portfolio/             # state tracking, drawdown management
│   ├── backtest/              # execution sim, walk-forward, Monte Carlo
│   └── notifications/         # Telegram bot (polling + webhook)
├── tests/                     # 100% line + branch coverage
├── docs/                      # architecture, strategy, standards
└── deploy/                    # example cron, systemd, Lambda configs
```

---

## Roadmap

| Phase | What | Status |
|-------|------|--------|
| **1** | Gold swing trading — signal pipeline, backtesting, validation, Telegram bot | 🔨 In progress |
| **2** | Add US stocks via IBKR — multi-asset portfolio, correlation controls | Planned |
| **3** | ML meta-model — conditional signal quality estimation | Planned |
| **4** | LLM sentiment — rare opportunity detection from news/social | Planned |

Phase 1 has a hard go/no-go gate: the strategy must pass walk-forward validation (>50% efficiency), Monte Carlo bootstrap (5th percentile positive), and a shuffled-price test (p < 0.01) before any live deployment. If it fails, we iterate or kill the approach. See [phase1-plan.md](docs/strategy/phase1-plan.md) for kill conditions.

---

## Contributing

This is a personal project, but the code is open source. If you find a bug or have a suggestion, open an issue. PRs welcome if they come with tests.

Before contributing, read [docs/coding-standards.md](docs/coding-standards.md). The short version: 100% test coverage, mypy --strict, ruff formatting, and dependency injection everywhere. No exceptions.

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

*Built with discipline, not hope. If the backtest says no edge, we don't trade.*

</div>
