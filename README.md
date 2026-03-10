# WealthOps

**An open-source gold swing trading advisory bot.**

Monitors XAU/USD daily candles, scores momentum via a composite signal, applies hard safety guards, and sends trade signals and daily briefings via Telegram. Runs on a Raspberry Pi. Does not execute trades — you decide, you act.

[![CI](https://github.com/mrdwan/wealthops/actions/workflows/ci.yml/badge.svg)](https://github.com/mrdwan/wealthops/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/wealthops.svg)](https://pypi.org/project/wealthops/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What It Does

- **Daily signal scan (23:00 UTC):** Fetches price data → calculates momentum composite → runs guard pipeline → sends a Telegram signal card if a trade fires.
- **Daily briefing (09:00 UTC):** Portfolio summary, risk health, market context.
- **Telegram commands:** `/status`, `/portfolio`, `/executed`, `/skip`, `/close`, `/risk`, `/help`

Strategy: Momentum Composite (RSI, trend, ATR, momentum, S/R) + 5 hard guards (macro gate, trend gate, event guard, pullback zone, drawdown gate). XAU/USD on IG spread betting — tax-free in Ireland.

---

## Installation

### On Raspberry Pi (production)

```bash
pip install wealthops
```

Then configure your secrets:

```bash
cp .env.example .env
# Edit .env with your Tiingo, FRED, and Telegram credentials
```

### For development

```bash
git clone https://github.com/mrdwan/wealthops.git
cd wealthops
uv sync --all-extras
uv run pre-commit install
```

---

## Quick Start

```bash
# Bootstrap historical data (first time only)
uv run python scripts/bootstrap_data.py

# Run a backtest
uv run python scripts/backtest_xauusd.py

# Run signal scan manually
wealthops ingest

# Run daily briefing manually
wealthops briefing
```

On the Pi, cron handles the scheduled runs:
```cron
0 23 * * 1-5  wealthops ingest 2>&1 | tee -a logs/cron.log
0  9 * * 1-5  wealthops briefing 2>&1 | tee -a logs/cron.log
```

---

## Architecture

```
XAU/USD daily data (Tiingo)
        │
        ▼
Indicators (RSI, EMAs, ADX, ATR, MACD)
        │
        ▼
Momentum Composite (5 components, z-scored, weighted)
        │
        ▼ (if BUY / STRONG_BUY)
Guard Pipeline (5 hard gates — all must pass)
        │
        ▼
Signal → Trap Order parameters + Position size
        │
        ▼
Telegram signal card
```

See [`docs/Architecture.md`](docs/Architecture.md) for the full reference.

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.12+ | Language |
| uv | Package management |
| pandas + pandas-ta | Data + indicators |
| pandera | Dataframe validation |
| Tiingo API | XAU/USD, DXY daily data |
| FRED API | VIX, yield curve, fed funds |
| python-telegram-bot | Telegram integration |
| pytest + ruff + mypy | Testing + code quality |
| Raspberry Pi | Deployment target |

---

## Project Status

Phase 1 — in development. See [`docs/phase1-plan.md`](docs/phase1-plan.md) for the build roadmap.

---

## License

MIT — see [LICENSE](LICENSE).
