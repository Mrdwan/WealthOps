"""Guard 3: Event Guard — no FOMC/NFP/CPI within 2 calendar days.

Implemented in Task 1C.
"""

from trading_advisor.guards.base import Guard, GuardResult


class EventGuard(Guard):
    """Blocks trading around major macro events (FOMC, NFP, CPI)."""

    @property
    def name(self) -> str:
        return "EventGuard"

    def evaluate(self, **kwargs: object) -> GuardResult:
        raise NotImplementedError("EventGuard.evaluate — Task 1C")
