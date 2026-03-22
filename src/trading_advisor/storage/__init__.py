"""Storage backends for WealthOps data persistence."""

from __future__ import annotations

from trading_advisor.storage.base import StorageBackend
from trading_advisor.storage.local import LocalStorage

__all__ = ["StorageBackend", "LocalStorage"]
