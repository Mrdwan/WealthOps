# Plan: Packaging & Deployment (Task 1H)

## Goal

Add S3 storage backend, replace the raw sys.argv CLI with click, add `backtest` and `health` commands, update pyproject.toml with `[aws]` extra, and provide deployment config templates (cron, systemd, Lambda, Docker, EventBridge).

## Decisions

- **click over typer** — click is already mentioned in architecture.md, has fewer transitive deps, and the CLI is simple enough that typer's auto-generation adds no value.
- **health.py as a separate module** — the staleness check has real logic that must be covered by tests. cli.py and runner.py are excluded from coverage, so the logic lives in health.py.
- **Heartbeat persisted to storage** — ingest and briefing already write to storage. After each run, we write `state/heartbeat` JSON with a timestamp. The health command reads it.
- **Bootstrap = start_date override** — the DataIngestor already handles incremental updates. `--bootstrap` just passes `2015-01-01` instead of the default `2020-01-01`.
- **cli.py excluded from coverage** — same policy as runner.py. It's pure wiring. All testable logic is in separate modules.
- **S3Storage import is lazy** — config.py imports S3Storage only when `storage_type="s3"`. No conditional import in `__init__.py`. Avoids hard dependency on boto3.
- **Tasks 1H.10–1H.12 are manual** — deployment, monitoring setup, and autonomous verification require real infrastructure. They're documented but not automated.

## File Map

- `src/trading_advisor/storage/s3.py` — S3Storage backend (behind `[aws]` extra)
- `src/trading_advisor/cli.py` — click-based CLI entry point
- `src/trading_advisor/health.py` — heartbeat staleness check
- `src/trading_advisor/runner.py` — modified: public functions, bootstrap, heartbeat persistence
- `src/trading_advisor/config.py` — modified: handle storage_type="s3"
- `src/trading_advisor/data/ingest.py` — modified: start_date parameter on run_daily_ingest
- `pyproject.toml` — modified: click dep, [aws] extra, entry point, coverage exclusion
- `tests/test_s3_storage.py` — S3Storage tests (mock boto3)
- `tests/test_health.py` — health check tests
- `tests/test_config.py` — modified: update s3 test expectations
- `tests/test_ingest.py` — modified: add start_date parameter test
- `deploy/crontab.example` — cron schedule template
- `deploy/wealthops-bot.service` — systemd unit template
- `deploy/lambda/handler.py` — Lambda handler template
- `deploy/lambda/Dockerfile` — Docker image for Lambda
- `deploy/eventbridge.json` — EventBridge schedule rules

## Tasks

### Task 1: S3Storage backend (1H.1)

- **Files**: `src/trading_advisor/storage/s3.py` (new), `src/trading_advisor/config.py` (modify), `tests/test_s3_storage.py` (new), `tests/test_config.py` (modify)
- **Action**:
  1. Read `src/trading_advisor/storage/base.py` for the ABC contract and `src/trading_advisor/storage/local.py` for the implementation pattern.
  2. Create `src/trading_advisor/storage/s3.py` implementing `StorageBackend`:
     - Constructor: `__init__(self, bucket: str, prefix: str = "") -> None`
     - Lazy-import boto3 in `__init__`. If missing, raise `ImportError("S3Storage requires boto3. Install with: pip install wealthops[aws]")`.
     - Store `self._bucket`, `self._prefix`, `self._client = boto3.client("s3")`.
     - Helper `_s3_key(self, key: str, ext: str) -> str`: joins prefix + key + ext with `/`. If prefix is empty, just `f"{key}.{ext}"`.
     - `read_parquet`: `get_object` → read Body → `pq.read_table(io.BytesIO(body)).to_pandas()`. Catch `ClientError` with code `NoSuchKey` → raise `FileNotFoundError`.
     - `write_parquet`: `pa.Table.from_pandas(df)` → write to `io.BytesIO` → `put_object`.
     - `read_json`: `get_object` → `json.loads(body.decode("utf-8"))`. Same error handling.
     - `write_json`: `json.dumps(data).encode("utf-8")` → `put_object`.
     - `exists`: try `head_object` for both `.parquet` and `.json` keys. Catch `ClientError` with HTTP 404 → return False. Return True if either exists.
     - Full type annotations, Google-style docstrings, `mypy --strict` clean.
  3. Modify `src/trading_advisor/config.py` `create_storage()`:
     - Add branch: `if settings.storage_type == "s3": from trading_advisor.storage.s3 import S3Storage; return S3Storage(bucket=settings.s3_bucket)`.
     - Update error message to list both "local" and "s3".
  4. Create `tests/test_s3_storage.py`:
     - Mock `boto3.client` using `mocker.patch("trading_advisor.storage.s3.boto3")`.
     - Test parquet roundtrip: capture `put_object` call body, return it in `get_object` mock.
     - Test JSON roundtrip: same pattern.
     - Test `exists` returns False then True.
     - Test read missing key: mock `get_object` to raise `ClientError` with code `NoSuchKey` → assert `FileNotFoundError`.
     - Test boto3 not installed: mock `builtins.__import__` to raise `ImportError` for boto3 → assert `ImportError` with "pip install wealthops[aws]".
     - Test prefix: verify `_s3_key("ohlcv/XAUUSD_daily", "parquet")` with prefix="data" → `"data/ohlcv/XAUUSD_daily.parquet"`.
     - Test no prefix: verify same key without prefix → `"ohlcv/XAUUSD_daily.parquet"`.
  5. Modify `tests/test_config.py`:
     - Change `test_create_storage_raises_for_unknown_type` to use `storage_type="gcs"` instead of `"s3"`.
     - Add `test_create_storage_returns_s3_storage`: mock `boto3.client`, create Settings with `storage_type="s3"`, `s3_bucket="test-bucket"`, assert `isinstance(backend, S3Storage)`.
- **Test**: `uv run pytest tests/test_s3_storage.py tests/test_config.py -v --no-cov`
- **Done when**: all 5 ABC methods work, boto3 import failure gives clear message, config routes to S3Storage, all tests green, mypy clean.
- [x] Completed

### Task 2: CLI + pyproject.toml (1H.2–1H.5, 1H.8)

- **Files**: `src/trading_advisor/cli.py` (new), `pyproject.toml` (modify), `src/trading_advisor/runner.py` (modify), `src/trading_advisor/data/ingest.py` (modify), `tests/test_ingest.py` (modify)
- **Action**:
  1. Read these files for current state: `src/trading_advisor/runner.py`, `src/trading_advisor/data/ingest.py`, `pyproject.toml`, `tests/test_ingest.py`.
  2. Modify `pyproject.toml`:
     - Add `"click>=8.1"` to `dependencies`.
     - Add `[project.optional-dependencies]` section `aws = ["boto3>=1.34"]`.
     - Change `requires-python` from `">=3.14"` to `">=3.12"`.
     - Change entry point from `"trading_advisor.runner:main"` to `"trading_advisor.cli:main"`.
     - Add `"src/trading_advisor/cli.py"` to `[tool.coverage.run] omit` list.
  3. Modify `src/trading_advisor/data/ingest.py`:
     - Add optional `start_date` parameter to `run_daily_ingest`: `def run_daily_ingest(self, end_date: str, start_date: str | None = None) -> dict[str, ValidationResult]:`. Use `start = start_date or _DEFAULT_START` on the first line.
  4. Modify `src/trading_advisor/runner.py`:
     - Rename `_run_ingest` → `run_ingest`, `_run_briefing` → `run_briefing`, `_run_bot` → `run_bot`.
     - Add `bootstrap: bool = False` parameter to `run_ingest`. When True, pass `start_date="2015-01-01"` to `ingestor.run_daily_ingest()`.
     - After the heartbeat Telegram send in both `run_ingest` and `run_briefing`, add: `storage.write_json("state/heartbeat", {"command": command_name, "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat()})`. Use the local `storage` variable already in scope.
     - Remove the `main()` function and the `if __name__ == "__main__"` block.
  5. Create `src/trading_advisor/cli.py`:
     ```python
     """CLI entry point for WealthOps."""
     import sys
     import click

     @click.group()
     def main() -> None:
         """WealthOps — Gold swing trading advisory bot."""

     @main.command()
     @click.option("--bootstrap", is_flag=True, help="Fetch full history from 2015.")
     def ingest(*, bootstrap: bool) -> None:
         """Fetch data, compute indicators, scan for signals."""
         from trading_advisor.runner import run_ingest
         run_ingest(bootstrap=bootstrap)

     @main.command()
     def briefing() -> None:
         """Send daily portfolio briefing via Telegram."""
         from trading_advisor.runner import run_briefing
         run_briefing()

     @main.command()
     def bot() -> None:
         """Start the Telegram bot."""
         from trading_advisor.runner import run_bot
         run_bot()
     ```
     Use lazy imports inside each command to keep startup fast. Full type annotations. Module docstring.
  6. Add test to `tests/test_ingest.py`:
     - `test_run_daily_ingest_custom_start_date`: Create a `FakeOHLCVProvider` that records what `start` arg it receives. Call `run_daily_ingest("2024-12-31", start_date="2015-01-01")`. Assert the provider was called with start="2015-01-01" (not the default "2020-01-01").
- **Test**: `uv run pytest tests/test_ingest.py -v --no-cov`
- **Done when**: `uv run wealthops --help` shows group with ingest/briefing/bot commands, `--bootstrap` flag on ingest, mypy clean, tests green.
- [x] Completed

### Task 3: Backtest + Health commands (1H.6–1H.7)

- **Files**: `src/trading_advisor/health.py` (new), `src/trading_advisor/cli.py` (modify), `src/trading_advisor/runner.py` (modify), `tests/test_health.py` (new)
- **Action**:
  1. Read: `src/trading_advisor/cli.py` (from Task 2), `src/trading_advisor/backtest/__init__.py`, `src/trading_advisor/backtest/engine.py` (lines 555-600 for `run_backtest` signature), `src/trading_advisor/backtest/report.py` (lines 15-30 for `compute_metrics` and 408-425 for `generate_report`), `src/trading_advisor/runner.py` (for the ingest pipeline pattern).
  2. Create `src/trading_advisor/health.py`:
     ```python
     """System health check: heartbeat freshness monitoring."""
     import datetime
     from trading_advisor.storage.base import StorageBackend

     _MAX_AGE_HOURS: float = 14.0

     def check_health(
         storage: StorageBackend,
         *,
         max_age_hours: float = _MAX_AGE_HOURS,
     ) -> tuple[bool, str]:
         """Check heartbeat freshness.

         Args:
             storage: Backend to read heartbeat state from.
             max_age_hours: Maximum acceptable age in hours.

         Returns:
             Tuple of (ok, message).
         """
         if not storage.exists("state/heartbeat"):
             return False, "No heartbeat found"
         heartbeat = storage.read_json("state/heartbeat")
         ts = datetime.datetime.fromisoformat(str(heartbeat["timestamp"]))
         now = datetime.datetime.now(tz=datetime.UTC)
         age_hours = (now - ts).total_seconds() / 3600
         if age_hours > max_age_hours:
             return False, f"STALE — last heartbeat {age_hours:.1f}h ago (threshold: {max_age_hours}h)"
         return True, f"OK — last heartbeat {age_hours:.1f}h ago"
     ```
  3. Add `run_backtest_report` function to `src/trading_advisor/runner.py`:
     - Load settings and create storage.
     - Read `ohlcv/XAUUSD_daily`, `ohlcv/EURUSD_daily`, `macro/FEDFUNDS` from storage.
     - Compute indicators + composite (same pattern as `run_ingest`).
     - Set up guards + guards_enabled (same pattern as `run_ingest`).
     - Add SMA_200 to EUR/USD (same pattern as `run_ingest`).
     - Call `run_backtest(indicators=composite_df, eurusd=eurusd_with_sma, guards=guards, guards_enabled=guards_enabled, fedfunds=fedfunds_series, starting_capital=_STARTING_CAPITAL)`.
     - Call `compute_metrics(result, fedfunds_series)`.
     - Call `generate_report(result, metrics)` → HTML string.
     - Write HTML to `output_path` parameter (default `"backtest_report.html"`).
     - Print summary: total trades, Sharpe, max DD, profit factor, win rate.
  4. Add commands to `src/trading_advisor/cli.py`:
     ```python
     @main.command()
     @click.option("--output", "-o", default="backtest_report.html", help="Output HTML report path.")
     def backtest(*, output: str) -> None:
         """Run backtest and generate HTML report."""
         from trading_advisor.runner import run_backtest_report
         run_backtest_report(output_path=output)

     @main.command()
     def health() -> None:
         """Check system health. Exit 0=OK, 1=stale/missing."""
         from trading_advisor.config import create_storage, load_settings
         from trading_advisor.health import check_health
         settings = load_settings()
         storage = create_storage(settings)
         ok, message = check_health(storage)
         click.echo(message)
         sys.exit(0 if ok else 1)
     ```
  5. Create `tests/test_health.py`:
     - Use `LocalStorage(tmp_path)` for storage.
     - `test_no_heartbeat_returns_false`: empty storage → `(False, "No heartbeat found")`.
     - `test_fresh_heartbeat_returns_true`: write heartbeat JSON with timestamp = 1 hour ago → `(True, "OK ...")`.
     - `test_stale_heartbeat_returns_false`: write heartbeat JSON with timestamp = 20 hours ago → `(False, "STALE ...")`.
     - `test_custom_max_age`: write heartbeat 5 hours old, `max_age_hours=4.0` → False. Same with `max_age_hours=6.0` → True.
     - Heartbeat JSON format: `{"command": "ingest", "timestamp": "2026-03-25T23:00:00+00:00"}`. Use `datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=N)` to generate test timestamps.
- **Test**: `uv run pytest tests/test_health.py -v --no-cov`
- **Done when**: `wealthops backtest --help` and `wealthops health --help` work, health check returns correct exit codes, mypy clean, tests green.
- [x] Completed

### Task 4: Deploy configs (1H.9)

- **Files**: `deploy/crontab.example` (new), `deploy/wealthops-bot.service` (new), `deploy/lambda/handler.py` (new), `deploy/lambda/Dockerfile` (new), `deploy/eventbridge.json` (new)
- **Action**:
  1. Read `docs/architecture.md` for the exact deployment specifications.
  2. Create `deploy/crontab.example`:
     ```cron
     # WealthOps scheduled jobs (Mon-Fri)
     # Data ingest + signal scan at 23:00 UTC
     0 23 * * 1-5  cd ~/wealthops && wealthops ingest 2>&1 | tee -a logs/cron.log
     # Daily briefing at 09:00 UTC
     0 9 * * 1-5   cd ~/wealthops && wealthops briefing 2>&1 | tee -a logs/cron.log
     ```
  3. Create `deploy/wealthops-bot.service`:
     ```ini
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
     EnvironmentFile=/home/pi/wealthops/.env

     [Install]
     WantedBy=multi-user.target
     ```
  4. Create `deploy/lambda/handler.py`:
     - Lambda handler that dispatches to runner functions based on event payload.
     - `def handler(event, context)`: reads `event["command"]` → calls `run_ingest()`, `run_briefing()`, or processes Telegram webhook update.
     - For webhook: reads `event["body"]` as Telegram update JSON.
  5. Create `deploy/lambda/Dockerfile`:
     - Base: `public.ecr.aws/lambda/python:3.12`
     - Install `wealthops[aws]`
     - Copy handler
     - Set CMD to handler
  6. Create `deploy/eventbridge.json`:
     - Two schedule rules: ingest at `cron(0 23 ? * MON-FRI *)` and briefing at `cron(0 9 ? * MON-FRI *)`.
     - Each targets the Lambda function with appropriate event payload.
- **Test**: No automated tests. Verify files exist and are syntactically valid.
- **Done when**: all 5 deploy config files exist with correct content matching architecture.md specs.
- [x] Completed
