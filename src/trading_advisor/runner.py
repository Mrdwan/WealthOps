"""Entry points for the WealthOps runner.

Commands:
  wealthops ingest    — fetch data + validate (23:00 UTC cron)
  wealthops briefing  — send daily briefing (09:00 UTC cron)
"""

import datetime
import sys


def _run_ingest() -> None:
    """Fetch all market and macro data, validate, and store."""
    from trading_advisor.config import create_storage, load_settings
    from trading_advisor.data.fred import FredProvider
    from trading_advisor.data.ingest import DataIngestor
    from trading_advisor.data.tiingo import TiingoProvider

    settings = load_settings()
    storage = create_storage(settings)
    ohlcv_provider = TiingoProvider(api_key=settings.tiingo_api_key)
    macro_provider = FredProvider(api_key=settings.fred_api_key)
    ingestor = DataIngestor(ohlcv_provider, macro_provider, storage)

    today = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d")
    print(f"[ingest] Running daily ingest up to {today} ...")

    results = ingestor.run_daily_ingest(end_date=today)

    for symbol, result in results.items():
        status = "OK" if result.valid else "FAILED"
        warnings = f" ({len(result.warnings)} warnings)" if result.warnings else ""
        print(f"  {symbol}: {status}{warnings}")
        for err in result.errors:
            print(f"    ERROR: {err}")
        for warn in result.warnings:
            print(f"    WARN:  {warn}")

    print("[ingest] Done.")


def main() -> None:
    """CLI entry point dispatched by pyproject.toml [project.scripts]."""
    commands = ("ingest", "briefing")
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: wealthops [{' | '.join(commands)}]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "ingest":
        _run_ingest()
    else:
        print(f"[wealthops] command='{command}' — not yet implemented.")
        sys.exit(0)


if __name__ == "__main__":
    main()
