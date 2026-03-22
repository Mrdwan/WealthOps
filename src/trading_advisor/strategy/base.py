"""Abstract Strategy base class.

Implemented in Task 1D.
"""

from abc import ABC, abstractmethod


class Strategy(ABC):
    """Abstract base class for all trading strategies."""

    @abstractmethod
    def generate_signals(self, **kwargs: object) -> list[object]:
        """Generate trade signals given current market data."""
        ...
