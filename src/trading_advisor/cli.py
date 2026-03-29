"""CLI entry point for WealthOps.

All commands use lazy imports to keep startup fast.
"""

import sys

import click


@click.group()
def main() -> None:
    """WealthOps -- Gold swing trading advisory bot."""


@main.command()
@click.option("--bootstrap", is_flag=True, help="Fresh fetch from WEALTHOPS_BOOTSTRAP_START.")
def ingest(*, bootstrap: bool) -> None:
    """Fetch data, compute indicators, and scan for signals."""
    from trading_advisor.runner import run_ingest  # noqa: PLC0415

    run_ingest(bootstrap=bootstrap)


@main.command()
def briefing() -> None:
    """Send daily portfolio briefing via Telegram."""
    from trading_advisor.runner import run_briefing  # noqa: PLC0415

    run_briefing()


@main.command()
def bot() -> None:
    """Start the Telegram bot in polling mode."""
    from trading_advisor.runner import run_bot  # noqa: PLC0415

    run_bot()


@main.command()
@click.option("--output", "-o", default="backtest_report.html", help="Output HTML report path.")
@click.option(
    "--threshold", "-t", type=float, default=None, help="Composite buy threshold (default 1.5)."
)
def backtest(*, output: str, threshold: float | None) -> None:
    """Run backtest and generate HTML report."""
    from trading_advisor.runner import run_backtest_report  # noqa: PLC0415

    run_backtest_report(output_path=output, threshold=threshold)


@main.command()
def health() -> None:
    """Check system health. Exit 0=OK, 1=stale/missing."""
    from trading_advisor.config import create_storage, load_settings  # noqa: PLC0415
    from trading_advisor.health import check_health  # noqa: PLC0415

    settings = load_settings()
    storage = create_storage(settings)
    ok, message = check_health(storage)
    click.echo(message)
    sys.exit(0 if ok else 1)
