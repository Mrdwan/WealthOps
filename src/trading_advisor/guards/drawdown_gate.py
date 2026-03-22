"""Guard 5: Drawdown Gate — portfolio drawdown < 15%.

Halts all trading if portfolio is in deep drawdown.
Dynamic throttling: 8–12% → halve sizes; 12–15% → max 1 position; >15% → HALT.

Implemented in Task 1C.
"""

from trading_advisor.guards.base import Guard, GuardResult


class DrawdownGate(Guard):
    """Blocks or restricts trading based on current portfolio drawdown."""

    @property
    def name(self) -> str:
        return "DrawdownGate"

    def evaluate(self, **kwargs: object) -> GuardResult:
        raise NotImplementedError("DrawdownGate.evaluate — Task 1C")
