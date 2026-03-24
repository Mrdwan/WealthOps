"""Guard 3: Event Guard — no FOMC/NFP/CPI within 2 calendar days.

Blocks trading in a 5-calendar-day exclusion window around major macro
events: 2 days before + event day + 2 days after.
"""

import datetime
import json
from collections.abc import Sequence
from pathlib import Path

from trading_advisor.guards.base import Guard, GuardResult


def load_calendar(path: Path) -> list[datetime.date]:
    """Load and merge all event dates from an economic calendar JSON file.

    The JSON file must have top-level keys (e.g. ``"fomc"``, ``"nfp"``,
    ``"cpi"``), each mapping to a list of ISO-format date strings.  A
    ``"_comment"`` key is ignored if present.

    Args:
        path: Path to the economic calendar JSON file.

    Returns:
        Sorted, deduplicated list of all event dates.
    """
    with open(path) as f:
        data: dict[str, object] = json.load(f)
    dates: set[datetime.date] = set()
    for key, values in data.items():
        if key.startswith("_"):
            continue
        if not isinstance(values, list):
            continue
        for v in values:
            if isinstance(v, str):
                dates.add(datetime.date.fromisoformat(v))
    return sorted(dates)


class EventGuard(Guard):
    """Blocks trading around major macro events (FOMC, NFP, CPI).

    Args:
        event_dates: Pre-loaded flat list of all event dates.
    """

    def __init__(self, event_dates: Sequence[datetime.date]) -> None:
        self._event_dates = event_dates

    @property
    def name(self) -> str:
        return "EventGuard"

    def evaluate(self, **kwargs: object) -> GuardResult:
        """Evaluate the Event Guard.

        Args:
            **kwargs: Must contain ``evaluation_date`` (:class:`datetime.date`).

        Returns:
            GuardResult with passed=True if no events are within 2 calendar
            days of the evaluation date.
        """
        evaluation_date = kwargs["evaluation_date"]
        if not isinstance(evaluation_date, datetime.date):
            msg = f"evaluation_date must be datetime.date, got {type(evaluation_date)}"
            raise TypeError(msg)
        for event_date in self._event_dates:
            if abs((evaluation_date - event_date).days) <= 2:
                return GuardResult(
                    passed=False,
                    guard_name=self.name,
                    reason=(
                        f"Event on {event_date.isoformat()} is"
                        f" {abs((evaluation_date - event_date).days)}d"
                        f" from {evaluation_date.isoformat()}"
                    ),
                )
        return GuardResult(
            passed=True,
            guard_name=self.name,
            reason="No events within 2 days",
        )
