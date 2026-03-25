"""Abstract Guard base class and GuardResult dataclass.

Implemented in Task 1C.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardResult:
    """Result of a single guard evaluation."""

    passed: bool
    guard_name: str
    reason: str  # e.g. "DXY at 104.2, above 200 SMA (103.8)"


class Guard(ABC):
    """Abstract base class for all hard guards."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable guard name."""
        ...

    @abstractmethod
    def evaluate(self, **kwargs: object) -> GuardResult:
        """Evaluate the guard and return a pass/fail result."""
        ...
