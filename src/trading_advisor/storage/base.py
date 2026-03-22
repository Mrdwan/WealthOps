"""Abstract base class for storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class StorageBackend(ABC):
    """Contract for all storage backends.

    Every backend must support reading and writing both Parquet and JSON
    data, and reporting whether a given key already exists.
    """

    @abstractmethod
    def read_parquet(self, key: str) -> pd.DataFrame:
        """Read a Parquet file identified by *key*.

        Args:
            key: Logical identifier for the stored data (path relative to
                the backend root, without extension).

        Returns:
            The DataFrame stored under *key*.

        Raises:
            FileNotFoundError: If no Parquet file exists for *key*.
        """

    @abstractmethod
    def write_parquet(self, key: str, df: pd.DataFrame) -> None:
        """Persist *df* as a Parquet file identified by *key*.

        Args:
            key: Logical identifier for the stored data.
            df: DataFrame to persist.
        """

    @abstractmethod
    def read_json(self, key: str) -> dict[str, Any]:
        """Read a JSON file identified by *key*.

        Args:
            key: Logical identifier for the stored data (without extension).

        Returns:
            The dictionary stored under *key*.

        Raises:
            FileNotFoundError: If no JSON file exists for *key*.
        """

    @abstractmethod
    def write_json(self, key: str, data: dict[str, Any]) -> None:
        """Persist *data* as a JSON file identified by *key*.

        Args:
            key: Logical identifier for the stored data.
            data: Dictionary to persist.
        """

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if a file (parquet or JSON) exists for *key*.

        Args:
            key: Logical identifier to check.

        Returns:
            True when a corresponding file is found, False otherwise.
        """
