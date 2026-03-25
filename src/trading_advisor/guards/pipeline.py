"""Guard pipeline runner: evaluates all enabled guards and collects results."""

from collections.abc import Sequence

from trading_advisor.guards.base import Guard, GuardResult


def run_guards(
    guards: Sequence[Guard],
    enabled: dict[str, bool],
    **kwargs: object,
) -> list[GuardResult]:
    """Evaluate all guards, skipping disabled ones.

    Args:
        guards: Ordered sequence of guard instances to evaluate.
        enabled: Maps guard name to on/off. Missing key = enabled (default True).
        **kwargs: Forwarded to each guard's ``evaluate()`` method.

    Returns:
        One ``GuardResult`` per guard. Disabled guards get
        ``GuardResult(passed=True, ..., reason="SKIPPED (disabled)")``.
    """
    results: list[GuardResult] = []
    for guard in guards:
        if not enabled.get(guard.name, True):
            results.append(
                GuardResult(
                    passed=True,
                    guard_name=guard.name,
                    reason="SKIPPED (disabled)",
                )
            )
        else:
            results.append(guard.evaluate(**kwargs))
    return results
