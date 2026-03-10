# WealthOps — Architecture

## Purpose of This Document

This is the technical architecture reference for WealthOps, a gold swing trading advisory system. It's written primarily for AI assistants working on the codebase, so they understand how the system fits together, where things live, and why decisions were made.

---

## System Overview

WealthOps is a single-user trading advisory system distributed as a PyPI package. It monitors XAU/USD daily candles, scores momentum, checks safety guards, and sends trade signals and daily briefings via Telegram. It does not execute trades. The user reads the signal, decides whether to act, and manually places orders on IG.

The package is infrastructure-agnostic. It runs on a laptop, a Raspberry Pi, or AWS Lambda. The deployment target only affects how you schedule jobs and where data is stored. Strategy logic is identical everywhere.

There are three jobs, exposed as CLI commands:

1. **`wealthops ingest`** — Fetches the day's price data, calculates indicators and the momentum composite, runs the guard pipeline, and sends a Telegram signal card if a trade fires. Scheduled at 23:00 UTC Mon-Fri.
2. **`wealthops briefing`** — Sends a portfolio summary, risk health, market context, and any pending signals to Telegram. Scheduled at 09:00 UTC Mon-Fri.
3. **`wealthops bot`** — Runs the Telegram command handler. Responds to user commands like `/status`, `/executed`, `/skip`, `/close`, `/risk`, `/portfolio`, `/help`. Runs as a long-lived process (polling) or as a stateless webhook handler (Lambda).

Additional CLI commands:
- **`wealthops backtest`** — Run the full backtest suite.
- **`wealthops health`** — Print health status (for UptimeRobot or monitoring).

---

## Infrastructure

### Package

```
pip install wealthops          # local/Pi deployment (LocalStorage)
pip install wealthops[aws]     # adds boto3 for S3Storage
```

### Core Stack

| Component | Tool |
|-----------|------|
| Python | 3.12+ |
| Package manager | uv |
| CLI | click or typer |
| Config | Environment variables (WEALTHOPS_*), loaded via python-dotenv |
| Version control | Git (GitHub repo) |

### External Services

| Service | Purpose | Tier |
|---------|---------|------|
| Tiingo API | XAU/USD and EUR/USD daily OHLCV (forex endpoint) | Free (50 req/hour) |
| FRED API | VIX, T10Y2Y, FEDFUNDS | Free |
| Telegram Bot API | Alerts, briefings, commands | Free |
| UptimeRobot | Dead man's switch — pings `wealthops health` endpoint | Free (5-min checks) |

### Storage Abstraction

The package never reads/writes files directly. All I/O goes through `StorageBackend`:

```python
class StorageBackend(ABC):
    def read_parquet(self, key: str) -> pd.DataFrame: ...
    def write_parquet(self, key: str, df: pd.DataFrame): ...
    def read_json(self, key: str) -> dict: ...
    def write_json(self, key: str, data: dict): ...
```

Two implementations:

| Backend | Env var | Where data lives | Install |
|---------|---------|-------------------|---------|
| `LocalStorage` | `WEALTHOPS_STORAGE=local` | `WEALTHOPS_DATA_DIR` (default: `./data`) | Default |
| `S3Storage` | `WEALTHOPS_STORAGE=s3` | `WEALTHOPS_S3_BUCKET` | `pip install wealthops[aws]` |

`config.py` reads `WEALTHOPS_STORAGE` and instantiates the correct backend. Every module receives the storage backend via dependency injection, never imports a concrete implementation.

### Environment Variables

All configuration comes from env vars. No config files are part of the package.

```
# Required
WEALTHOPS_TIINGO_API_KEY=...
WEALTHOPS_FRED_API_KEY=...
WEALTHOPS_TELEGRAM_BOT_TOKEN=...
WEALTHOPS_TELEGRAM_CHAT_ID=...

# Optional
WEALTHOPS_STORAGE=local                    # "local" (default) or "s3"
WEALTHOPS_DATA_DIR=./data                  # for local storage
WEALTHOPS_S3_BUCKET=my-bucket              # for S3 storage
WEALTHOPS_TELEGRAM_MODE=polling            # "polling" (default) or "webhook"
WEALTHOPS_TELEGRAM_HEARTBEAT_CHAT_ID=...   # separate channel for heartbeats
WEALTHOPS_LOG_LEVEL=INFO
```

On a laptop/Pi, these live in a `.env` file. On AWS, use SSM Parameter Store or Lambda env vars.

---

## Data Flow

```
23:00 UTC cron trigger
        │
        ▼
┌─────────────────┐
│  Data Ingest     │  Fetch today's candle from Tiingo (XAU/USD, EUR/USD)
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
│                  │    1. Macro Gate — EUR/USD > 200 SMA? (weak dollar)
│                  │    2. Trend Gate — ADX(14) > 20?
│                  │    3. Event Guard — no FOMC/NFP/CPI within 2 days?
│                  │    4. Pullback Zone — close within 2% of EMA_8?
│                  │    5. Drawdown Gate — portfolio drawdown < 15%?
│                  │  Only enabled guards run (see GUARDS_ENABLED in config).
│                  │  All enabled guards must pass. Any fail = no signal.
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

## Directory Structure

```
wealthops/
├── pyproject.toml                  # uv managed, PyPI package config
├── uv.lock
├── .env                            # API keys, env config (gitignored, not part of package)
├── src/
│   └── trading_advisor/
│       ├── __init__.py
│       ├── config.py               # Loads WEALTHOPS_* env vars, instantiates storage backend
│       ├── cli.py                  # CLI entry points: ingest, briefing, bot, backtest, health
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── base.py             # StorageBackend ABC
│       │   ├── local.py            # LocalStorage (default)
│       │   └── s3.py               # S3Storage (optional, requires [aws] extra)
│       ├── data/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract DataProvider
│       │   ├── tiingo.py           # Tiingo: XAU/USD, EUR/USD
│       │   └── fred.py             # FRED: VIX, T10Y2Y, FEDFUNDS
│       ├── indicators/
│       │   ├── __init__.py
│       │   ├── technical.py        # RSI, EMA, ADX, ATR, MACD, wick ratios
│       │   └── composite.py        # Momentum composite (5 components, z-score, weights)
│       ├── guards/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract Guard + GuardResult + GUARDS_ENABLED config
│       │   ├── macro_gate.py       # EUR/USD > 200 SMA (inverted DXY proxy)
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
│       │   └── manager.py          # Portfolio state, drawdown tracking (uses StorageBackend)
│       ├── notifications/
│       │   ├── __init__.py
│       │   └── telegram.py         # Bot (polling + webhook), commands, signal cards, briefings
│       ├── backtest/
│       │   ├── __init__.py
│       │   ├── engine.py           # Execution simulation (trap orders, partial exits, time stops)
│       │   ├── validation.py       # Walk-forward, Monte Carlo, shuffled-price
│       │   └── report.py           # Metrics + charts
│       └── runner.py               # Orchestrator: fetch → analyze → notify
├── tests/
│   ├── test_indicators.py
│   ├── test_composite.py
│   ├── test_guards.py
│   ├── test_signals.py
│   ├── test_sizing.py
│   ├── test_storage.py
│   └── test_notifications.py
├── scripts/
│   ├── backtest_xauusd.py          # Run full backtest
│   └── bootstrap_data.py           # Initial historical data download
├── data/                            # Default local data dir (gitignored)
│   ├── ohlcv/
│   │   ├── XAUUSD_daily.parquet
│   │   └── EURUSD_daily.parquet
│   ├── macro/
│   │   ├── VIX.parquet
│   │   ├── T10Y2Y.parquet
│   │   └── FEDFUNDS.parquet
│   ├── calendars/
│   │   └── economic_calendar.json  # Manually maintained, updated every 3-6 months
│   └── state/
│       └── portfolio.json          # Current portfolio state
├── logs/                            # Rotating logs (gitignored)
│   └── wealthops.log
└── deploy/                          # Example deployment configs (not part of package)
    ├── wealthops-bot.service        # systemd unit file (Pi/Linux)
    ├── crontab.example              # cron schedule example
    ├── lambda/                      # AWS Lambda handler + Dockerfile
    └── eventbridge.json             # EventBridge schedule config
```

---

## Scheduling

The package exposes CLI commands. How you schedule them depends on your deployment.

### Option A: Laptop / Raspberry Pi (cron)

```cron
# Data ingest + signal scan
0 23 * * 1-5  cd ~/wealthops && wealthops ingest 2>&1 | tee -a logs/cron.log

# Daily briefing
0 9 * * 1-5   cd ~/wealthops && wealthops briefing 2>&1 | tee -a logs/cron.log
```

Monday through Friday only. Gold doesn't trade on weekends.

### Option B: AWS (EventBridge + Lambda)

Two EventBridge Scheduler rules trigger a Lambda function with different event payloads:
- 23:00 UTC Mon-Fri → `{"command": "ingest"}`
- 09:00 UTC Mon-Fri → `{"command": "briefing"}`

The Lambda handler imports `trading_advisor.runner` and calls the appropriate function. Example handler in `deploy/lambda/`.

---

## Telegram Bot

The bot supports two modes, controlled by `WEALTHOPS_TELEGRAM_MODE`:

**Polling (default)** — For laptop/Pi. Runs as a long-lived process. No public IP, domain, or SSL cert needed. `python-telegram-bot` polls the Telegram API for updates.

**Webhook** — For AWS Lambda. Stateless. Telegram sends updates to a Lambda Function URL. The Lambda handler processes one update per invocation.

### Polling mode (systemd example for Pi/Linux)

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
ExecStart=wealthops bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

systemd handles restarts if the bot crashes. `Restart=always` with a 10-second delay.

### Webhook mode (Lambda)

The Lambda Function URL receives Telegram updates as HTTP POST requests. The handler parses the update and calls the same command-processing logic as polling mode. See `deploy/lambda/` for the handler template.

---

## Portfolio State

Stored as a JSON object at key `state/portfolio`. The portfolio manager reads and writes through `StorageBackend`, so this is a local file on disk with `LocalStorage` or an S3 object with `S3Storage`. The format is the same either way.

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

The portfolio manager reads this state, updates it, and writes it back via `StorageBackend`. No database. Locking isn't needed because only one process writes at a time (either the scheduled job or the Telegram bot, and the bot only writes in response to user commands which are sequential). On S3, last-write-wins is fine for a single user.

---

## Monitoring

### Heartbeat

After each successful cron run (ingest or briefing), the script sends a short message to a dedicated Telegram "heartbeat" channel:

```
✓ ingest 2026-03-10 23:00 UTC — 0.4s — XAU composite: 1.2σ NEUTRAL
```

If you stop seeing these messages, something broke.

### Dead Man's Switch

For laptop/Pi deployments: UptimeRobot (free tier) pings `wealthops health` every 5 minutes. The health command checks:

- Whether the last heartbeat was within the last 14 hours (covers overnight gap between 23:00 and 09:00)

If UptimeRobot gets no response, it sends you an email/push notification. This catches crashes, network outages, and hardware failures.

For AWS: CloudWatch alarms on Lambda errors. If the ingest or briefing Lambda fails, CloudWatch triggers an SNS notification to your email. The heartbeat Telegram messages still work as a secondary check.

### Logging

All scripts log to `logs/wealthops.log` using Python's logging module. Rotating file handler, 5MB per file, keep 5 files. Cron output also captured to `logs/cron.log`.

Log levels:
- INFO: successful ingest, signals generated, briefings sent, commands processed
- WARNING: data validation anomalies, guard edge cases, missed heartbeat
- ERROR: API failures, file I/O errors, unhandled exceptions

---

## Secrets

All secrets are environment variables with the `WEALTHOPS_` prefix. See the Environment Variables section above for the full list.

On laptop/Pi: stored in `.env` file, gitignored, loaded by `python-dotenv`.
On AWS: stored in SSM Parameter Store or Lambda environment variables.

No secrets in code. No secrets in git.

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

Deployment is not part of the package. The `deploy/` directory in the repo contains example configs for each target. The package itself only cares about env vars and the `wealthops` CLI.

### Option A: Laptop / Raspberry Pi

**First-time setup:**
1. Install the package: `pip install wealthops` (or `uv add wealthops`)
2. Create `.env` with `WEALTHOPS_*` env vars
3. Run `wealthops backtest` to validate strategy (laptop only, before deploying)
4. Run `wealthops ingest --bootstrap` to fetch historical data
5. Install cron jobs (see Scheduling section)
6. Start the Telegram bot as a systemd service (see Telegram Bot section) or run `wealthops bot` in a screen/tmux session
7. Set up UptimeRobot to ping `wealthops health`

**Updating:**
```bash
pip install --upgrade wealthops
sudo systemctl restart wealthops-bot
# Cron jobs pick up changes on next run
```

**Pi-specific notes:**
- Use a USB-booted SSD (128GB minimum), not an SD card. SD cards degrade with frequent writes.
- Ethernet preferred over WiFi for reliability.
- Pi 4 or 5, 4GB RAM is plenty (8GB if running other agents alongside).

### Option B: AWS

**Components:**
- ECR: Docker image with `wealthops[aws]` installed
- Lambda (ARM/Graviton2, 3GB RAM): runs ingest, briefing, and webhook handler
- EventBridge Scheduler: cron triggers for ingest (23:00 UTC) and briefing (09:00 UTC)
- Lambda Function URL: Telegram webhook endpoint
- S3: storage backend for parquet + portfolio JSON
- SSM Parameter Store: secrets

**First-time setup:**
1. Build Docker image from `deploy/lambda/Dockerfile`, push to ECR
2. Create S3 bucket, set `WEALTHOPS_STORAGE=s3` and `WEALTHOPS_S3_BUCKET=...`
3. Store secrets in SSM Parameter Store
4. Create Lambda function from ECR image
5. Create EventBridge schedules
6. Set Telegram webhook to Lambda Function URL
7. Run bootstrap data ingest

**Estimated cost: < $1/month.**

---

## Backtest vs Production

The backtest engine and the live runner share the same strategy code (indicators, composite, guards, sizing, signal generation). The difference is execution:

| Aspect | Backtest | Production |
|--------|----------|------------|
| Data source | Historical parquet files | Daily append from Tiingo/FRED |
| Execution | Simulated fills with spread + slippage + funding costs | Advisory only, user executes manually on IG |
| Portfolio state | In-memory, reset per run | JSON via StorageBackend, persistent |
| Trailing stop | Evaluated at daily close | User updates IG stop order each morning |
| Output | Metrics, equity curve, trade log | Telegram signal cards + briefings |

This separation is enforced by design. The strategy module never knows whether it's running in backtest or live mode. It receives market data and portfolio state, and returns signals. The runner and backtest engine handle the rest.

---

## What This Architecture Does NOT Include

- No broker API integration (Phase 2)
- No auto-execution of trades
- No database (JSON via StorageBackend is enough for one user, one asset)
- No ML models (Phase 3)
- No multi-asset support (Phase 2)
- No web dashboard
