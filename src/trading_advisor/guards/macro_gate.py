"""Guard 1: Macro Gate — DXY < 200 SMA (weak dollar favors gold).

Implemented in Task 1C.
"""

from trading_advisor.guards.base import Guard, GuardResult


class MacroGate(Guard):
    """Passes when the dollar is weak (DXY below its 200-day SMA)."""

    @property
    def name(self) -> str:
        return "MacroGate"

    def evaluate(self, **kwargs: object) -> GuardResult:
        raise NotImplementedError("MacroGate.evaluate — Task 1C")
