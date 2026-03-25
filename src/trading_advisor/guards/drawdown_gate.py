"""Guard 5: Drawdown Gate — portfolio drawdown < 15%.

Halts all trading if the portfolio is in deep drawdown.
Only checks the 15% halt threshold. Throttling at 8%/12% is handled
by the position sizing module, not here.
"""

from trading_advisor.guards.base import Guard, GuardResult


class DrawdownGate(Guard):
    """Blocks trading when portfolio drawdown reaches 15%."""

    @property
    def name(self) -> str:
        return "DrawdownGate"

    def evaluate(self, **kwargs: object) -> GuardResult:
        """Evaluate the Drawdown Gate.

        Args:
            **kwargs: Must contain ``drawdown`` (float) — the current
                portfolio drawdown as a fraction (e.g. 0.10 for 10%).

        Returns:
            GuardResult with passed=True if drawdown < 15%.
        """
        drawdown = float(kwargs["drawdown"])  # type: ignore[arg-type]
        passed = drawdown < 0.15
        op = "<" if passed else ">="
        reason = f"Drawdown {drawdown:.1%} {op} 15%"
        return GuardResult(passed=passed, guard_name=self.name, reason=reason)
