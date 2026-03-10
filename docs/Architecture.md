# WealthOps — Architecture

## Purpose of This Document

This is the technical architecture reference for WealthOps, a gold swing trading advisory system. It's written primarily for AI assistants working on the codebase, so they understand how the system fits together, where things live, and why decisions were made.

---

## System Overview

WealthOps is a single-user trading advisory bot that runs on a Raspberry Pi. It monitors XAU/USD daily candles, scores momentum, checks safety guards, and sends trade signals and daily briefings via Telegram. It does not execute trades. The user reads the signal, decides whether to act, and manually places orders on IG.

There are three jobs:

1. **Data ingest + signal scan** — runs at 23:00 UTC via cron. Fetches the day's price data, calculates indicators and the momentum composite, runs the guard pipeline, and sends a Telegram signal card if a trade fires.
2. **Daily briefing** — runs at 09:00 UTC via cron. Sends a portfolio summary, risk health, market context, and any pending signals to Telegram.
3. **Telegram command handler** — runs continuously as a systemd service. Responds to user commands like `/status`, `/executed`, `/skip`, `/close`, `/risk`, `/portfolio`, `/help`.

All three jobs share the same codebase but have different entry points.

---

## Infrastructure

### Hardware

- Raspberry Pi 4 or 5 (4GB RAM is plenty)
- USB-booted SSD (128GB minimum). No SD card for the OS or data — SD cards degrade with frequent writes. The SSD stores the OS, code, data, and state.
- Ethernet connection preferred over WiFi for reliability. The Pi sits next to the router.

### Software Stack

| Component | Tool |
|-----------|------|
| OS | Raspberry Pi OS Lite (64-bit, no desktop) |
| Python | 3.12+ |
| Package manager | uv |
| Scheduling | cron |
| Process management | systemd |
| Secrets | .env file, loaded via python-dotenv |
| Version control | Git (GitHub repo, deploy via git pull) |

### External Services

| Service | Purpose | Tier |
|---------|---------|------|
| Tiingo API | XAU/USD and DXY daily OHLCV | Free (50 req/hour) |
| FRED API | VIX, T10Y2Y, FEDFUNDS | Free |
| Telegram Bot API | Alerts, briefings, commands | Free |
| UptimeRobot | Dead man's switch — pings a health endpoint on the Pi | Free (5-min checks) |

No AWS services in Phase 1. No databases. No containers. No cloud.

---

## Data Flow

```
23:00 UTC cron trigger
        │
        ▼
┌─────────────────┐
│  Data Ingest     │  Fetch today's candle from Tiingo (XAU/USD, DXY)
│                  │  Fetch macro data from FRED (VIX, T10Y2Y, FEDFUNDS)
│                  │  Validate (OHLCV sanity checks, no gaps, no nulls)
│                  │  Append to local parquet files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Indicators      │  Calculate full feature vector (RSI, EMAs, ADX, ATR, etc.)
│                  │  Calculate momentum composite (5 components, z-scored
│                  │  over rolling 252-day window, weighted sum)
│                  │  Classify signal: STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Guard Pipeline  │  If composite >= BUY:
│                  │    1. Macro Gate — DXY < 200 SMA?
│                  │    2. Trend Gate — ADX(14) > 20?
│                  │    3. Event Guard — no FOMC/NFP/CPI within 2 days?
│                  │    4. Pullback Zone — close within 2% of EMA_8?
│                  │    5. Drawdown Gate — portfolio drawdown < 15%?
│                  │  All must pass. Any fail = no signal.
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Signal Gen      │  If all guards pass:
│                  │    Calculate Trap Order prices (buy stop, limit)
│                  │    Calculate stop loss, take profit, trailing stop params
│                  │    Calculate position size (dual-constraint)
│                  │    Check partial position rule (trailing 50% blocks new entries)
│                  │  Package into a Signal object.
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Notify          │  Send Telegram signal card with all trade details.
│                  │  Update heartbeat timestamp.
└─────────────────┘


09:00 UTC cron trigger
        │
        ▼
┌─────────────────┐
│  Daily Briefing  │  Read portfolio state JSON.
│                  │  Read latest market data from parquet.
│                  │  Format and send briefing to Telegram.
│                  │  Update heartbeat timestamp.
└─────────────────┘
```

---

## Directory Structure (on the Pi)

```
~/wealthops/
├── pyproject.toml
├── uv.lock
├── .env                            # API keys, Telegram bot token (gitignored)
├── src/
│   └── trading_advisor/
│       ├── __init__.py
│       ├── config.py               # Asset configs, risk params, loads .env
│       ├── data/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract DataProvider
│       │   ├── tiingo.py           # Tiingo: XAU/USD, DXY
│       │   └── fred.py             # FRED: VIX, T10Y2Y, FEDFUNDS
│       ├── indicators/
│       │   ├── __init__.py
│       │   ├── technical.py        # RSI, EMA, ADX, ATR, MACD, wick ratios
│       │   └── composite.py        # Momentum composite (5 components, z-score, weights)
│       ├── guards/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract Guard + GuardResult
│       │   ├── macro_gate.py       # DXY < 200 SMA
│       │   ├── trend_gate.py       # ADX > 20
│       │   ├── event_guard.py      # No FOMC/NFP/CPI within 2 days
│       │   ├── pullback_zone.py    # Close within 2% of EMA_8
│       │   └── drawdown_gate.py    # Portfolio drawdown < 15%
│       ├── strategy/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract Strategy
│       │   ├── swing_sniper.py     # Composite + guards + trap order logic
│       │   └── sizing.py           # Dual-constraint position sizing
│       ├── portfolio/
│       │   ├── __init__.py
│       │   └── manager.py          # Portfolio state, drawdown tracking, JSON persistence
│       ├── notifications/
│       │   ├── __init__.py
│       │   └── telegram.py         # Bot, commands, signal cards, briefings
│       ├── backtest/
│       │   ├── __init__.py
│       │   ├── engine.py           # Execution simulation (trap orders, partial exits, time stops)
│       │   ├── validation.py       # Walk-forward, Monte Carlo, shuffled-price
│       │   └── report.py           # Metrics + charts
│       └── runner.py               # Entry points: ingest, briefing, scan
├── tests/
│   ├── test_indicators.py
│   ├── test_composite.py
│   ├── test_guards.py
│   ├── test_signals.py
│   ├── test_sizing.py
│   └── test_notifications.py
├── scripts/
│   ├── backtest_xauusd.py          # Run full backtest
│   └── bootstrap_data.py           # Initial historical data download
├── data/                            # Local parquet + state (gitignored)
│   ├── ohlcv/
│   │   ├── XAUUSD_daily.parquet
│   │   └── DXY_daily.parquet
│   ├── macro/
│   │   ├── VIX.parquet
│   │   ├── T10Y2Y.parquet
│   │   └── FEDFUNDS.parquet
│   ├── calendars/
│   │   └── economic_calendar.json  # Manually maintained, updated every 3-6 months
│   └── state/
│       └── portfolio.json          # Current portfolio state
└── logs/
    └── wealthops.log               # Rotating log file
```

---

## Scheduling (cron)

```cron
# Data ingest + signal scan
0 23 * * 1-5  cd ~/wealthops && uv run python -m trading_advisor.runner ingest 2>&1 | tee -a logs/cron.log

# Daily briefing
0 9 * * 1-5   cd ~/wealthops && uv run python -m trading_advisor.runner briefing 2>&1 | tee -a logs/cron.log
```

Monday through Friday only. Gold doesn't trade on weekends.

---

## Telegram Bot (systemd)

The Telegram bot runs as a long-lived process using polling (not webhooks). Polling is simpler on a Pi since you don't need a public IP, domain, or SSL cert.

```ini
# /etc/systemd/system/wealthops-bot.service
[Unit]
Description=WealthOps Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/wealthops
ExecStart=/home/pi/.local/bin/uv run python -m trading_advisor.notifications.telegram
Restart=always
RestartSec=10
Environment=DOTENV_PATH=/home/pi/wealthops/.env

[Install]
WantedBy=multi-user.target
```

systemd handles restarts if the bot crashes. `Restart=always` with a 10-second delay.

---

## Portfolio State

Stored as a single JSON file at `data/state/portfolio.json`. Updated when the user sends Telegram commands (`/executed`, `/close`, `/skip`).

```json
{
  "cash": 15000.00,
  "starting_capital": 15000.00,
  "high_water_mark": 15000.00,
  "positions": [
    {
      "id": "sig_20260310_xauusd",
      "asset": "XAU/USD",
      "direction": "LONG",
      "entry_price": 2352.00,
      "entry_date": "2026-03-10",
      "size_lots": 0.05,
      "stop_loss": 2310.00,
      "take_profit": 2410.00,
      "trailing_stop": 2330.00,
      "tp_50_hit": false,
      "risk_amount": 210.00,
      "days_held": 3
    }
  ],
  "closed_trades": [],
  "drawdown_pct": 0.0,
  "throttle_level": "normal",
  "last_updated": "2026-03-10T09:00:00Z"
}
```

The portfolio manager reads this file, updates it, and writes it back. No database. File locking isn't needed because only one process writes at a time (either the cron job or the Telegram bot, and the Telegram bot only writes in response to user commands which are sequential).

---

## Monitoring

### Heartbeat

After each successful cron run (ingest or briefing), the script sends a short message to a dedicated Telegram "heartbeat" channel:

```
✓ ingest 2026-03-10 23:00 UTC — 0.4s — XAU composite: 1.2σ NEUTRAL
```

If you stop seeing these messages, something broke.

### Dead Man's Switch

UptimeRobot (free tier) pings a simple HTTP health endpoint on the Pi every 5 minutes. The endpoint is a minimal Flask/FastAPI server (or just a static file served by Python's http.server) that returns 200 if:

- The Telegram bot systemd service is running
- The last cron heartbeat was within the last 14 hours (covers overnight gap between 23:00 and 09:00)

If UptimeRobot gets no response, it sends you an email/push notification. This catches Pi crashes, network outages, and SSD failures.

### Logging

All scripts log to `logs/wealthops.log` using Python's logging module. Rotating file handler, 5MB per file, keep 5 files. Cron output also captured to `logs/cron.log`.

Log levels:
- INFO: successful ingest, signals generated, briefings sent, commands processed
- WARNING: data validation anomalies, guard edge cases, missed heartbeat
- ERROR: API failures, file I/O errors, unhandled exceptions

---

## Secrets

All secrets live in `~/wealthops/.env`, gitignored.

```
TIINGO_API_KEY=...
FRED_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_HEARTBEAT_CHAT_ID=...
```

Loaded by `python-dotenv` in `config.py`. No secrets in code, no secrets in git.

---

## Economic Calendar

Maintained manually as `data/calendars/economic_calendar.json`. Updated every 3-6 months.

```json
{
  "fomc": ["2026-01-29", "2026-03-19", "2026-05-07", "2026-06-18", "..."],
  "nfp": ["2026-01-03", "2026-02-07", "2026-03-06", "..."],
  "cpi": ["2026-01-14", "2026-02-12", "2026-03-12", "..."]
}
```

The Event Guard checks if today is within 2 calendar days of any date in these lists. NFP is always the first Friday of the month. FOMC and CPI dates are published by the Fed and BLS a year in advance. This is simpler and more reliable than adding another API dependency.

---

## Deployment

### First-Time Setup

1. Flash Raspberry Pi OS Lite (64-bit) to SSD, boot from USB
2. SSH in, install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. Clone the repo: `git clone git@github.com:<user>/wealthops.git ~/wealthops`
4. Create `.env` with API keys
5. `cd ~/wealthops && uv sync`
6. Run `uv run python scripts/bootstrap_data.py` to fetch historical data
7. Install cron jobs (see Scheduling section)
8. Enable and start the Telegram bot service:
   ```
   sudo cp wealthops-bot.service /etc/systemd/system/
   sudo systemctl enable wealthops-bot
   sudo systemctl start wealthops-bot
   ```
9. Set up UptimeRobot to ping the health endpoint

### Updating

```bash
ssh pi@<pi-ip>
cd ~/wealthops
git pull
uv sync
sudo systemctl restart wealthops-bot
```

Cron jobs pick up code changes automatically on next run. The Telegram bot needs a restart.

---

## Backtest vs Production

The backtest engine and the live runner share the same strategy code (indicators, composite, guards, sizing, signal generation). The difference is execution:

| Aspect | Backtest | Production |
|--------|----------|------------|
| Data source | Historical parquet files | Daily append from Tiingo/FRED |
| Execution | Simulated fills with spread + slippage + funding costs | Advisory only, user executes manually on IG |
| Portfolio state | In-memory, reset per run | JSON file, persistent |
| Trailing stop | Evaluated at daily close | User updates IG stop order each morning |
| Output | Metrics, equity curve, trade log | Telegram signal cards + briefings |

This separation is enforced by design. The strategy module never knows whether it's running in backtest or live mode. It receives market data and portfolio state, and returns signals. The runner and backtest engine handle the rest.

---

## What This Architecture Does NOT Include

- No broker API integration (Phase 2)
- No auto-execution of trades
- No database (JSON file is enough for one user, one asset)
- No Docker or containers
- No cloud services
- No ML models (Phase 3)
- No multi-asset support (Phase 2)
- No web dashboard

---

## Migration Path to AWS (If Needed Later)

If the Pi becomes unreliable or Phase 2 needs more infrastructure:

- Cron jobs → Lambda + EventBridge
- Parquet files on SSD → S3
- Portfolio JSON → DynamoDB
- Telegram bot polling → Lambda Function URL webhook
- Systemd → ECS Fargate (if long-running process needed)
- .env → SSM Parameter Store

The code is designed so that only the data I/O layer and deployment config change. Strategy logic stays identical.
