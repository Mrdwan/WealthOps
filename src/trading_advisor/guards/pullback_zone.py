"""Guard 4: Pullback Zone — (close - EMA_8) / EMA_8 <= 2%.

Filters out chasing extended moves. Only enter near the EMA.

Implemented in Task 1C.
"""

from trading_advisor.guards.base import Guard, GuardResult


class PullbackZone(Guard):
    """Passes when price is within 2% of EMA_8 (not extended)."""

    @property
    def name(self) -> str:
        return "PullbackZone"

    def evaluate(self, **kwargs: object) -> GuardResult:
        raise NotImplementedError("PullbackZone.evaluate — Task 1C")
