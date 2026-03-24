"""Guard 2: Trend Gate — ADX(14) > 20 (trending market required)."""

from trading_advisor.guards.base import Guard, GuardResult


class TrendGate(Guard):
    """Passes when the market is trending (ADX above 20)."""

    @property
    def name(self) -> str:
        return "TrendGate"

    def evaluate(self, **kwargs: object) -> GuardResult:
        """Evaluate the Trend Gate.

        Args:
            **kwargs: Must contain ``adx`` (float).

        Returns:
            GuardResult with passed=True if ADX > 20.
        """
        adx = float(kwargs["adx"])  # type: ignore[arg-type]
        passed = adx > 20.0
        return GuardResult(
            passed=passed,
            guard_name=self.name,
            reason=f"ADX {adx:.1f} {'>' if passed else '<='} 20",
        )
