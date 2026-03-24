"""Integration test: all 5 guards wired through the pipeline runner."""

import datetime

from trading_advisor.guards import (
    DrawdownGate,
    EventGuard,
    Guard,
    MacroGate,
    PullbackZone,
    TrendGate,
    run_guards,
)


def _make_guards() -> list[Guard]:
    """Create all 5 guards with test-friendly config."""
    event_dates = [datetime.date(2024, 6, 12)]  # single FOMC
    return [
        MacroGate(),
        TrendGate(),
        EventGuard(event_dates),
        PullbackZone(),
        DrawdownGate(),
    ]


# Kwargs that make all guards pass
_ALL_PASS_KWARGS: dict[str, object] = {
    "eurusd_close": 1.10,
    "eurusd_sma_200": 1.05,
    "adx": 25.0,
    "evaluation_date": datetime.date(2024, 1, 15),  # far from events
    "close": 2050.0,
    "ema_8": 2040.0,
    "drawdown": 0.05,
}


class TestGuardIntegration:
    """Integration tests: full guard pipeline end-to-end."""

    def test_all_guards_pass(self) -> None:
        """All 5 guards pass → signal is valid."""
        guards = _make_guards()
        enabled = {g.name: True for g in guards}
        results = run_guards(guards, enabled, **_ALL_PASS_KWARGS)
        assert len(results) == 5
        assert all(r.passed for r in results)

    def test_single_guard_fails(self) -> None:
        """ADX below threshold → TrendGate fails, others pass."""
        guards = _make_guards()
        enabled = {g.name: True for g in guards}
        kwargs = {**_ALL_PASS_KWARGS, "adx": 18.0}
        results = run_guards(guards, enabled, **kwargs)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 1
        assert failed[0].guard_name == "TrendGate"

    def test_multiple_guards_fail(self) -> None:
        """ADX=18 + extended pullback → 2 failures."""
        guards = _make_guards()
        enabled = {g.name: True for g in guards}
        kwargs = {**_ALL_PASS_KWARGS, "adx": 18.0, "close": 2200.0}
        results = run_guards(guards, enabled, **kwargs)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 2
        names = {r.guard_name for r in failed}
        assert names == {"TrendGate", "PullbackZone"}

    def test_disabled_guard_skipped(self) -> None:
        """Disable MacroGate → SKIPPED, others evaluated."""
        guards = _make_guards()
        enabled = {g.name: True for g in guards}
        enabled["MacroGate"] = False
        results = run_guards(guards, enabled, **_ALL_PASS_KWARGS)
        macro_result = next(r for r in results if r.guard_name == "MacroGate")
        assert macro_result.passed is True
        assert "SKIPPED" in macro_result.reason
        # Others still evaluated normally
        non_skipped = [r for r in results if "SKIPPED" not in r.reason]
        assert len(non_skipped) == 4
        assert all(r.passed for r in non_skipped)

    def test_all_disabled_all_pass(self) -> None:
        """Every guard disabled → all SKIPPED → signal valid."""
        guards = _make_guards()
        enabled = {g.name: False for g in guards}
        results = run_guards(guards, enabled, **_ALL_PASS_KWARGS)
        assert all(r.passed for r in results)
        assert all("SKIPPED" in r.reason for r in results)

    def test_reason_strings_informative(self) -> None:
        """Reason strings contain actual values, not just pass/fail."""
        guards = _make_guards()
        enabled = {g.name: True for g in guards}
        results = run_guards(guards, enabled, **_ALL_PASS_KWARGS)
        for result in results:
            assert len(result.reason) > 5  # not empty/trivial
