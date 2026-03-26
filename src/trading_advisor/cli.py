"""CLI entry point for WealthOps.

All commands use lazy imports to keep startup fast.
"""

import click


@click.group()
def main() -> None:
    """WealthOps -- Gold swing trading advisory bot."""


@main.command()
@click.option("--bootstrap", is_flag=True, help="Fetch full history from 2015.")
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
