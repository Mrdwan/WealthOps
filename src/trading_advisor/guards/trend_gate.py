"""Guard 2: Trend Gate — ADX(14) > 20 (trending market required).

Implemented in Task 1C.
"""

from trading_advisor.guards.base import Guard, GuardResult


class TrendGate(Guard):
    """Passes when the market is trending (ADX above threshold)."""

    @property
    def name(self) -> str:
        return "TrendGate"

    def evaluate(self, **kwargs: object) -> GuardResult:
        raise NotImplementedError("TrendGate.evaluate — Task 1C")
