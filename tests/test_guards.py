"""Tests for guard infrastructure: GuardResult, Guard ABC, and pipeline runner."""

import dataclasses
import datetime
import json
from pathlib import Path

import pytest

from trading_advisor.guards.base import Guard, GuardResult
from trading_advisor.guards.drawdown_gate import DrawdownGate
from trading_advisor.guards.event_guard import EventGuard, load_calendar
from trading_advisor.guards.macro_gate import MacroGate
from trading_advisor.guards.pipeline import run_guards
from trading_advisor.guards.pullback_zone import PullbackZone
from trading_advisor.guards.trend_gate import TrendGate


class _StubGuard(Guard):
    """Concrete guard for testing the pipeline."""

    def __init__(self, guard_name: str, result: GuardResult) -> None:
        self._name = guard_name
        self._result = result

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, **kwargs: object) -> GuardResult:
        return self._result


class _KwargsCapturingGuard(Guard):
    """Guard that captures kwargs and reflects them in the result reason."""

    def __init__(self, guard_name: str) -> None:
        self._name = guard_name

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, **kwargs: object) -> GuardResult:
        adx = kwargs.get("adx")
        return GuardResult(passed=True, guard_name=self._name, reason=f"adx={adx}")


def test_guard_result_construction() -> None:
    """GuardResult stores all three fields correctly."""
    result = GuardResult(passed=True, guard_name="TestGuard", reason="all good")

    assert result.passed is True
    assert result.guard_name == "TestGuard"
    assert result.reason == "all good"


def test_guard_result_frozen() -> None:
    """GuardResult is immutable — assignment must raise FrozenInstanceError."""
    result = GuardResult(passed=True, guard_name="TestGuard", reason="all good")

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.passed = False  # type: ignore[misc]


def test_guard_abc_not_instantiable() -> None:
    """Guard ABC cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Guard()  # type: ignore[abstract]


def test_run_guards_all_pass() -> None:
    """All enabled guards pass → all results have passed=True."""
    guard_a = _StubGuard("A", GuardResult(passed=True, guard_name="A", reason="ok"))
    guard_b = _StubGuard("B", GuardResult(passed=True, guard_name="B", reason="ok"))

    results = run_guards([guard_a, guard_b], enabled={"A": True, "B": True})

    assert len(results) == 2
    assert all(r.passed for r in results)


def test_run_guards_one_fails() -> None:
    """Guard A passes and Guard B fails → results reflect that."""
    guard_a = _StubGuard("A", GuardResult(passed=True, guard_name="A", reason="ok"))
    guard_b = _StubGuard("B", GuardResult(passed=False, guard_name="B", reason="fail"))

    results = run_guards([guard_a, guard_b], enabled={"A": True, "B": True})

    assert results[0].passed is True
    assert results[1].passed is False


def test_run_guards_disabled_skipped() -> None:
    """Disabled guard gets a SKIPPED result; enabled guard is still evaluated."""
    guard_a = _StubGuard("A", GuardResult(passed=False, guard_name="A", reason="fail"))
    guard_b = _StubGuard("B", GuardResult(passed=False, guard_name="B", reason="fail"))

    results = run_guards([guard_a, guard_b], enabled={"B": False})

    # Guard A is not in enabled dict → defaults to enabled → evaluated normally
    assert results[0].passed is False
    # Guard B is disabled → skipped with passed=True
    assert results[1].passed is True
    assert "SKIPPED" in results[1].reason


def test_run_guards_all_disabled() -> None:
    """All disabled guards produce SKIPPED results with passed=True."""
    guard_a = _StubGuard("A", GuardResult(passed=False, guard_name="A", reason="fail"))
    guard_b = _StubGuard("B", GuardResult(passed=False, guard_name="B", reason="fail"))

    results = run_guards([guard_a, guard_b], enabled={"A": False, "B": False})

    assert all(r.passed for r in results)
    assert all("SKIPPED" in r.reason for r in results)


def test_run_guards_missing_key_defaults_enabled() -> None:
    """Guard not present in enabled dict is treated as enabled and evaluated."""
    guard_c = _StubGuard("C", GuardResult(passed=False, guard_name="C", reason="nope"))

    results = run_guards([guard_c], enabled={})

    assert len(results) == 1
    assert results[0].passed is False
    assert results[0].reason == "nope"


def test_run_guards_kwargs_forwarded() -> None:
    """kwargs passed to run_guards are forwarded to each guard's evaluate()."""
    guard = _KwargsCapturingGuard("KwargsGuard")

    results = run_guards([guard], {}, adx=25.0)

    assert len(results) == 1
    assert "25.0" in results[0].reason


# ---------------------------------------------------------------------------
# MacroGate
# ---------------------------------------------------------------------------


class TestMacroGate:
    """Tests for Guard 1: Macro Gate (EUR/USD close > EUR/USD 200 SMA)."""

    def test_pass_eurusd_above_sma(self) -> None:
        gate = MacroGate()
        result = gate.evaluate(eurusd_close=1.10, eurusd_sma_200=1.05)
        assert result.passed is True
        assert result.guard_name == "MacroGate"
        assert "1.1000" in result.reason
        assert "1.0500" in result.reason

    def test_fail_eurusd_below_sma(self) -> None:
        gate = MacroGate()
        result = gate.evaluate(eurusd_close=1.02, eurusd_sma_200=1.05)
        assert result.passed is False
        assert "<=" in result.reason

    def test_fail_eurusd_exactly_at_sma(self) -> None:
        gate = MacroGate()
        result = gate.evaluate(eurusd_close=1.05, eurusd_sma_200=1.05)
        assert result.passed is False  # not strictly >

    def test_name(self) -> None:
        assert MacroGate().name == "MacroGate"


# ---------------------------------------------------------------------------
# TrendGate
# ---------------------------------------------------------------------------


class TestTrendGate:
    """Tests for Guard 2: Trend Gate (ADX > 20)."""

    def test_pass_adx_above_threshold(self) -> None:
        gate = TrendGate()
        result = gate.evaluate(adx=25.0)
        assert result.passed is True
        assert result.guard_name == "TrendGate"
        assert "25.0" in result.reason

    def test_fail_adx_below_threshold(self) -> None:
        gate = TrendGate()
        result = gate.evaluate(adx=15.0)
        assert result.passed is False
        assert "<=" in result.reason

    def test_fail_adx_exactly_20(self) -> None:
        gate = TrendGate()
        result = gate.evaluate(adx=20.0)
        assert result.passed is False  # not strictly >

    def test_pass_adx_barely_above(self) -> None:
        gate = TrendGate()
        result = gate.evaluate(adx=20.01)
        assert result.passed is True

    def test_name(self) -> None:
        assert TrendGate().name == "TrendGate"


# ---------------------------------------------------------------------------
# EventGuard
# ---------------------------------------------------------------------------


class TestEventGuard:
    """Tests for Guard 3: Event Guard (5-day exclusion window)."""

    def _guard(self, *dates: datetime.date) -> EventGuard:
        return EventGuard(list(dates))

    def test_pass_3_days_before(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 17))
        assert result.passed is True

    def test_fail_2_days_before(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 18))
        assert result.passed is False

    def test_fail_1_day_before(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 19))
        assert result.passed is False

    def test_fail_day_of(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 20))
        assert result.passed is False
        assert "0d" in result.reason

    def test_fail_1_day_after(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 21))
        assert result.passed is False

    def test_fail_2_days_after(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 22))
        assert result.passed is False

    def test_pass_3_days_after(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 23))
        assert result.passed is True

    def test_pass_between_distant_events(self) -> None:
        guard = self._guard(
            datetime.date(2024, 1, 10),
            datetime.date(2024, 1, 20),
        )
        result = guard.evaluate(evaluation_date=datetime.date(2024, 1, 15))
        assert result.passed is True  # 5 days from both

    def test_empty_calendar_always_passes(self) -> None:
        guard = self._guard()  # no events
        result = guard.evaluate(evaluation_date=datetime.date(2024, 6, 15))
        assert result.passed is True

    def test_name(self) -> None:
        assert self._guard().name == "EventGuard"

    def test_reason_contains_event_date(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        result = guard.evaluate(evaluation_date=datetime.date(2024, 3, 18))
        assert "2024-03-20" in result.reason

    def test_raises_on_non_date_evaluation_date(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        with pytest.raises(TypeError, match="evaluation_date must be"):
            guard.evaluate(evaluation_date="2024-03-18")

    def test_raises_on_missing_evaluation_date(self) -> None:
        guard = self._guard(datetime.date(2024, 3, 20))
        with pytest.raises(KeyError):
            guard.evaluate()


class TestLoadCalendar:
    """Tests for the load_calendar helper."""

    def test_load_merges_and_deduplicates(self, tmp_path: Path) -> None:
        cal = {
            "fomc": ["2024-03-20", "2024-06-12"],
            "nfp": ["2024-03-08", "2024-03-20"],  # 03-20 duplicated
            "cpi": ["2024-03-12"],
            "_comment": "should be ignored",
            "_notes": ["2024-12-25"],  # underscore key with list value — still ignored
        }
        p = tmp_path / "cal.json"
        p.write_text(json.dumps(cal))
        dates = load_calendar(p)
        assert len(dates) == 4  # 5 entries, 1 duplicate = 4 unique; _notes date excluded
        assert dates == sorted(dates)  # sorted

    def test_load_empty_calendar(self, tmp_path: Path) -> None:
        cal: dict[str, list[str]] = {"fomc": [], "nfp": [], "cpi": []}
        p = tmp_path / "cal.json"
        p.write_text(json.dumps(cal))
        dates = load_calendar(p)
        assert dates == []


# ---------------------------------------------------------------------------
# PullbackZone
# ---------------------------------------------------------------------------


class TestPullbackZone:
    """Tests for Guard 4: Pullback Zone ((close - EMA_8) / EMA_8 <= 2%)."""

    def test_pass_small_positive_distance(self) -> None:
        """close=2050, ema_8=2030 → distance=20/2030≈0.00985 → pass."""
        guard = PullbackZone()
        result = guard.evaluate(close=2050.0, ema_8=2030.0)
        assert result.passed is True
        assert result.guard_name == "PullbackZone"

    def test_fail_extended(self) -> None:
        """close=2100, ema_8=2030 → distance=70/2030≈0.03448 → fail."""
        guard = PullbackZone()
        result = guard.evaluate(close=2100.0, ema_8=2030.0)
        assert result.passed is False
        assert ">" in result.reason

    def test_pass_exactly_2_percent(self) -> None:
        """close=102.0, ema_8=100.0 → distance=2/100=0.02 exactly → pass."""
        guard = PullbackZone()
        result = guard.evaluate(close=102.0, ema_8=100.0)
        assert result.passed is True  # <= 0.02

    def test_fail_barely_above_2_percent(self) -> None:
        """close=102.1, ema_8=100 → distance=0.021 → fail."""
        guard = PullbackZone()
        result = guard.evaluate(close=102.1, ema_8=100.0)
        assert result.passed is False

    def test_pass_negative_distance(self) -> None:
        """close=2000, ema_8=2030 → distance=-30/2030≈-0.01478 → pass."""
        guard = PullbackZone()
        result = guard.evaluate(close=2000.0, ema_8=2030.0)
        assert result.passed is True  # negative = below EMA = not chasing

    def test_reason_contains_distance(self) -> None:
        guard = PullbackZone()
        result = guard.evaluate(close=2050.0, ema_8=2030.0)
        assert "0.0099" in result.reason  # 20/2030 ≈ 0.009852...

    def test_reason_contains_threshold(self) -> None:
        guard = PullbackZone()
        result = guard.evaluate(close=2050.0, ema_8=2030.0)
        assert "0.02" in result.reason

    def test_name(self) -> None:
        assert PullbackZone().name == "PullbackZone"


# ---------------------------------------------------------------------------
# DrawdownGate
# ---------------------------------------------------------------------------


class TestDrawdownGate:
    """Tests for Guard 5: Drawdown Gate (drawdown < 15%)."""

    def test_pass_no_drawdown(self) -> None:
        gate = DrawdownGate()
        result = gate.evaluate(drawdown=0.0)
        assert result.passed is True
        assert result.guard_name == "DrawdownGate"

    def test_pass_moderate_drawdown(self) -> None:
        gate = DrawdownGate()
        result = gate.evaluate(drawdown=0.149)
        assert result.passed is True

    def test_fail_at_threshold(self) -> None:
        gate = DrawdownGate()
        result = gate.evaluate(drawdown=0.15)
        assert result.passed is False  # strict < 15%

    def test_fail_deep_drawdown(self) -> None:
        gate = DrawdownGate()
        result = gate.evaluate(drawdown=0.20)
        assert result.passed is False

    def test_reason_contains_percentage(self) -> None:
        gate = DrawdownGate()
        result = gate.evaluate(drawdown=0.10)
        assert "10.0%" in result.reason

    def test_name(self) -> None:
        assert DrawdownGate().name == "DrawdownGate"
