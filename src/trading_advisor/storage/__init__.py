"""Storage backends for WealthOps data persistence."""

from trading_advisor.storage.base import StorageBackend
from trading_advisor.storage.local import LocalStorage

__all__ = ["StorageBackend", "LocalStorage"]
