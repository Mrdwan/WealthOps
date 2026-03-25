"""Guard 4: Pullback Zone — (close - EMA_8) / EMA_8 <= 2%.

Filters out chasing extended moves. Only enter near the EMA.
Negative distance passes intentionally (below EMA = not chasing).
"""

from trading_advisor.guards.base import Guard, GuardResult


class PullbackZone(Guard):
    """Passes when price is within 2% of EMA_8 (not extended)."""

    @property
    def name(self) -> str:
        return "PullbackZone"

    def evaluate(self, **kwargs: object) -> GuardResult:
        """Evaluate the Pullback Zone guard.

        Args:
            **kwargs: Must contain ``close`` (float) and ``ema_8`` (float).

        Returns:
            GuardResult with passed=True if pullback distance <= 2%.
        """
        close = float(kwargs["close"])  # type: ignore[arg-type]
        ema_8 = float(kwargs["ema_8"])  # type: ignore[arg-type]
        distance = (close - ema_8) / ema_8
        passed = distance <= 0.02
        op = "<=" if passed else ">"
        reason = f"Pullback distance {distance:.4f} {op} 0.02"
        return GuardResult(passed=passed, guard_name=self.name, reason=reason)
