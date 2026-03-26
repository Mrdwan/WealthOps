"""S3-backed storage backend."""

from __future__ import annotations

import io
import json
from typing import Any, cast

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from trading_advisor.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """S3-backed storage. Requires boto3 (install with: pip install wealthops[aws]).

    Keys are mapped to S3 object keys as ``{prefix}/{key}.{ext}`` when a prefix
    is given, or ``{key}.{ext}`` when the prefix is empty.  Parquet files use a
    ``.parquet`` extension; JSON files use a ``.json`` extension.

    Args:
        bucket: Name of the S3 bucket to read from and write to.
        prefix: Optional path prefix prepended to every object key.
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        """Initialise the backend.

        Args:
            bucket: S3 bucket name.
            prefix: Optional prefix for all object keys.

        Raises:
            ImportError: If boto3 is not installed.
        """
        try:
            import boto3
            from botocore.exceptions import ClientError as _ClientError
        except ImportError as exc:
            raise ImportError(
                "S3Storage requires boto3. Install with: pip install wealthops[aws]"
            ) from exc

        self._bucket = bucket
        self._prefix = prefix
        self._client: Any = boto3.client("s3")
        self._client_error: type[Exception] = _ClientError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _s3_key(self, key: str, ext: str) -> str:
        """Return the full S3 object key for the given logical *key* and extension.

        Args:
            key: Logical data identifier (no extension).
            ext: File extension without leading dot (e.g. ``"parquet"``).

        Returns:
            The S3 object key string.
        """
        filename = f"{key}.{ext}"
        if self._prefix:
            return f"{self._prefix}/{filename}"
        return filename

    # ------------------------------------------------------------------
    # StorageBackend implementation
    # ------------------------------------------------------------------

    def read_parquet(self, key: str) -> pd.DataFrame:
        """Read a Parquet object from S3 identified by *key*.

        Args:
            key: Logical identifier (no extension).

        Returns:
            The DataFrame stored under *key*.

        Raises:
            FileNotFoundError: If the S3 object does not exist.
        """
        s3_key = self._s3_key(key, "parquet")
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=s3_key)
        except self._client_error as exc:
            error_code = exc.response["Error"]["Code"]  # type: ignore[attr-defined]
            if error_code == "NoSuchKey":
                raise FileNotFoundError(
                    f"S3 object not found: s3://{self._bucket}/{s3_key}"
                ) from exc
            raise
        body: bytes = response["Body"].read()
        return cast(pd.DataFrame, pq.read_table(io.BytesIO(body)).to_pandas())

    def write_parquet(self, key: str, df: pd.DataFrame) -> None:
        """Persist *df* as a Parquet object in S3.

        Args:
            key: Logical identifier for the stored data.
            df: DataFrame to persist.
        """
        s3_key = self._s3_key(key, "parquet")
        buf = io.BytesIO()
        pq.write_table(pa.Table.from_pandas(df), buf)
        self._client.put_object(Bucket=self._bucket, Key=s3_key, Body=buf.getvalue())

    def read_json(self, key: str) -> dict[str, Any]:
        """Read a JSON object from S3 identified by *key*.

        Args:
            key: Logical identifier (no extension).

        Returns:
            The dictionary stored under *key*.

        Raises:
            FileNotFoundError: If the S3 object does not exist.
        """
        s3_key = self._s3_key(key, "json")
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=s3_key)
        except self._client_error as exc:
            error_code = exc.response["Error"]["Code"]  # type: ignore[attr-defined]
            if error_code == "NoSuchKey":
                raise FileNotFoundError(
                    f"S3 object not found: s3://{self._bucket}/{s3_key}"
                ) from exc
            raise
        body: bytes = response["Body"].read()
        result: dict[str, Any] = json.loads(body)
        return result

    def write_json(self, key: str, data: dict[str, Any]) -> None:
        """Persist *data* as a JSON object in S3.

        Args:
            key: Logical identifier for the stored data.
            data: Dictionary to persist.
        """
        s3_key = self._s3_key(key, "json")
        body = json.dumps(data).encode()
        self._client.put_object(Bucket=self._bucket, Key=s3_key, Body=body)

    def exists(self, key: str) -> bool:
        """Return True if a Parquet or JSON object exists in S3 for *key*.

        Args:
            key: Logical identifier to check.

        Returns:
            True when a corresponding S3 object is found, False otherwise.
        """
        for ext in ("parquet", "json"):
            s3_key = self._s3_key(key, ext)
            try:
                self._client.head_object(Bucket=self._bucket, Key=s3_key)
                return True
            except self._client_error as exc:
                error_code = exc.response["Error"]["Code"]  # type: ignore[attr-defined]
                if error_code != "404":
                    raise
        return False
