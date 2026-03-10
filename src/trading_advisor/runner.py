"""Entry points for the WealthOps runner.

Commands:
  wealthops ingest    — fetch data + run signal scan (23:00 UTC cron)
  wealthops briefing  — send daily briefing (09:00 UTC cron)

Implemented in Task 1G/1H.
"""

from __future__ import annotations

import sys


def main() -> None:
    """CLI entry point dispatched by pyproject.toml [project.scripts]."""
    commands = ("ingest", "briefing")
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: wealthops [{' | '.join(commands)}]")
        sys.exit(1)

    command = sys.argv[1]
    print(f"[wealthops] command='{command}' — not yet implemented.")
    sys.exit(0)


if __name__ == "__main__":
    main()
