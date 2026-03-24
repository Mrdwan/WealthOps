"""Guard 1: Macro Gate — EUR/USD close > EUR/USD 200 SMA.

Weak dollar (EUR/USD above its long-term average) favors gold longs.
"""

from trading_advisor.guards.base import Guard, GuardResult


class MacroGate(Guard):
    """Passes when EUR/USD is above its 200-day SMA (weak dollar)."""

    @property
    def name(self) -> str:
        return "MacroGate"

    def evaluate(self, **kwargs: object) -> GuardResult:
        """Evaluate the Macro Gate.

        Args:
            **kwargs: Must contain ``eurusd_close`` (float) and
                ``eurusd_sma_200`` (float).

        Returns:
            GuardResult with passed=True if EUR/USD close > 200 SMA.
        """
        eurusd_close = float(kwargs["eurusd_close"])  # type: ignore[arg-type]
        eurusd_sma_200 = float(kwargs["eurusd_sma_200"])  # type: ignore[arg-type]
        passed = eurusd_close > eurusd_sma_200
        op = ">" if passed else "<="
        reason = f"EUR/USD {eurusd_close:.4f} {op} 200 SMA ({eurusd_sma_200:.4f})"
        return GuardResult(passed=passed, guard_name=self.name, reason=reason)
