"""Tests for signal generation (composite + guards → Signal object).

Tasks: 1D — verify 5 historical signals against chart. Check trap order levels.
"""

import pytest

from trading_advisor.strategy.base import Strategy


class _ConcreteStrategy(Strategy):
    """Minimal concrete Strategy for testing the ABC contract."""

    def generate_signals(self, **kwargs: object) -> list[object]:
        return []


class TestStrategyABC:
    """Tests for the Strategy abstract base class."""

    def test_abc_not_instantiable(self) -> None:
        """Strategy ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Strategy()  # type: ignore[abstract]

    def test_concrete_subclass_instantiable(self) -> None:
        """A concrete subclass that implements generate_signals can be instantiated."""
        strategy = _ConcreteStrategy()
        assert isinstance(strategy, Strategy)

    def test_generate_signals_callable(self) -> None:
        """generate_signals returns a list."""
        strategy = _ConcreteStrategy()
        result = strategy.generate_signals()
        assert result == []
