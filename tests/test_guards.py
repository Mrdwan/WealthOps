"""Tests for guard infrastructure: GuardResult, Guard ABC, and pipeline runner."""

import dataclasses

import pytest

from trading_advisor.guards.base import Guard, GuardResult
from trading_advisor.guards.pipeline import run_guards


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
