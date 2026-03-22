"""Local filesystem storage backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from trading_advisor.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """Stores data on the local filesystem under a root directory.

    Keys are interpreted as relative path segments (forward-slash separated).
    Parquet files are stored with a ``.parquet`` extension; JSON files with
    a ``.json`` extension.  Parent directories are created automatically on
    write.

    Args:
        data_dir: Root directory under which all files are stored.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialise the backend with the given root directory.

        Args:
            data_dir: Root directory for all stored files.
        """
        self._data_dir = data_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, path: Path) -> Path:
        """Resolve *path* and verify it is inside ``self._data_dir``.

        Args:
            path: Candidate filesystem path to validate.

        Returns:
            The resolved path if it is within the data directory.

        Raises:
            ValueError: If the resolved path escapes the data directory.
        """
        resolved = path.resolve()
        if not resolved.is_relative_to(self._data_dir.resolve()):
            raise ValueError(f"Key resolves to a path outside the data directory: {resolved}")
        return resolved

    def _parquet_path(self, key: str) -> Path:
        """Return the full filesystem path for a parquet *key*.

        Args:
            key: Logical key (no extension).

        Returns:
            Absolute path ending in ``.parquet``.

        Raises:
            ValueError: If the key escapes the data directory.
        """
        return self._resolve(self._data_dir / f"{key}.parquet")

    def _json_path(self, key: str) -> Path:
        """Return the full filesystem path for a JSON *key*.

        Args:
            key: Logical key (no extension).

        Returns:
            Absolute path ending in ``.json``.

        Raises:
            ValueError: If the key escapes the data directory.
        """
        return self._resolve(self._data_dir / f"{key}.json")

    # ------------------------------------------------------------------
    # StorageBackend implementation
    # ------------------------------------------------------------------

    def read_parquet(self, key: str) -> pd.DataFrame:
        """Read a Parquet file identified by *key*.

        Args:
            key: Logical identifier (path relative to data_dir, no extension).

        Returns:
            The DataFrame stored under *key*.

        Raises:
            FileNotFoundError: If no Parquet file exists for *key*.
        """
        path = self._parquet_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Parquet file not found: {path}")
        return cast(pd.DataFrame, pq.read_table(path).to_pandas())

    def write_parquet(self, key: str, df: pd.DataFrame) -> None:
        """Persist *df* as a Parquet file identified by *key*.

        Parent directories are created automatically.

        Args:
            key: Logical identifier for the stored data.
            df: DataFrame to persist.
        """
        path = self._parquet_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(df), path)

    def read_json(self, key: str) -> dict[str, Any]:
        """Read a JSON file identified by *key*.

        Args:
            key: Logical identifier (path relative to data_dir, no extension).

        Returns:
            The dictionary stored under *key*.

        Raises:
            FileNotFoundError: If no JSON file exists for *key*.
        """
        path = self._json_path(key)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            result: dict[str, Any] = json.load(fh)
        return result

    def write_json(self, key: str, data: dict[str, Any]) -> None:
        """Persist *data* as a JSON file identified by *key*.

        Parent directories are created automatically.

        Args:
            key: Logical identifier for the stored data.
            data: Dictionary to persist.
        """
        path = self._json_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def exists(self, key: str) -> bool:
        """Return True if a file (parquet or JSON) exists for *key*.

        Args:
            key: Logical identifier to check.

        Returns:
            True when a corresponding file is found, False otherwise.
        """
        return self._parquet_path(key).exists() or self._json_path(key).exists()
