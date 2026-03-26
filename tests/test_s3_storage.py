"""Tests for S3Storage backend."""

import io
import sys
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# ---------------------------------------------------------------------------
# Fake ClientError for testing
# ---------------------------------------------------------------------------


class FakeClientError(Exception):
    """Mimics botocore.exceptions.ClientError."""

    def __init__(self, error_code: str) -> None:
        self.response: dict[str, Any] = {"Error": {"Code": error_code}}
        super().__init__(f"ClientError: {error_code}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> MagicMock:
    """Return a fresh MagicMock acting as the boto3 S3 client."""
    return MagicMock()


@pytest.fixture()
def _patch_boto3(monkeypatch: pytest.MonkeyPatch, mock_client: MagicMock) -> None:
    """Inject fake boto3 and botocore into sys.modules."""
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_client

    mock_botocore_exc = MagicMock()
    mock_botocore_exc.ClientError = FakeClientError

    mock_botocore = MagicMock()
    mock_botocore.exceptions = mock_botocore_exc

    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)
    monkeypatch.setitem(sys.modules, "botocore", mock_botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", mock_botocore_exc)

    # Force reimport so the patched modules are picked up
    monkeypatch.delitem(sys.modules, "trading_advisor.storage.s3", raising=False)


@pytest.fixture()
def storage(_patch_boto3: None, mock_client: MagicMock) -> Any:
    """Return an S3Storage pointed at 'test-bucket'."""
    from trading_advisor.storage.s3 import S3Storage  # noqa: PLC0415

    return S3Storage(bucket="test-bucket")


@pytest.fixture()
def storage_with_prefix(_patch_boto3: None, mock_client: MagicMock) -> Any:
    """Return an S3Storage with a non-empty prefix."""
    from trading_advisor.storage.s3 import S3Storage  # noqa: PLC0415

    return S3Storage(bucket="test-bucket", prefix="data")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df() -> pd.DataFrame:
    """Return a small DataFrame for roundtrip tests."""
    return pd.DataFrame({"open": [1.0, 2.0], "close": [1.1, 2.1]})


def _make_json() -> dict[str, Any]:
    """Return a small dict for JSON roundtrip tests."""
    return {"symbol": "XAUUSD", "count": 42}


def _df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Serialise *df* to Parquet bytes in the same way S3Storage does."""
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _s3_key
# ---------------------------------------------------------------------------


def test_s3_key_no_prefix(storage: Any) -> None:
    """`_s3_key` returns 'key.ext' when prefix is empty."""
    assert storage._s3_key("prices", "parquet") == "prices.parquet"


def test_s3_key_with_prefix(storage_with_prefix: Any) -> None:
    """`_s3_key` returns 'prefix/key.ext' when prefix is non-empty."""
    assert storage_with_prefix._s3_key("prices", "parquet") == "data/prices.parquet"


# ---------------------------------------------------------------------------
# write_parquet / read_parquet
# ---------------------------------------------------------------------------


def test_parquet_roundtrip(storage: Any, mock_client: MagicMock) -> None:
    """write_parquet followed by read_parquet reproduces the original DataFrame."""
    df = _make_df()

    storage.write_parquet("prices", df)

    # Capture the bytes that were uploaded
    call_args = mock_client.put_object.call_args
    body_bytes: bytes = call_args.kwargs["Body"]

    # Arrange get_object to return those same bytes
    mock_body = MagicMock()
    mock_body.read.return_value = body_bytes
    mock_client.get_object.return_value = {"Body": mock_body}

    result = storage.read_parquet("prices")

    pd.testing.assert_frame_equal(result, df)


def test_write_parquet_calls_put_object(storage: Any, mock_client: MagicMock) -> None:
    """write_parquet calls put_object with the correct bucket and key."""
    df = _make_df()
    storage.write_parquet("prices", df)

    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"] == "prices.parquet"
    assert isinstance(call_kwargs["Body"], bytes)


def test_read_parquet_missing_key_raises(storage: Any, mock_client: MagicMock) -> None:
    """`read_parquet` raises FileNotFoundError when the S3 object does not exist."""
    mock_client.get_object.side_effect = FakeClientError("NoSuchKey")

    with pytest.raises(FileNotFoundError, match="prices.parquet"):
        storage.read_parquet("prices")


def test_read_parquet_other_client_error_reraises(storage: Any, mock_client: MagicMock) -> None:
    """`read_parquet` re-raises ClientError when it is not a NoSuchKey error."""
    mock_client.get_object.side_effect = FakeClientError("AccessDenied")

    with pytest.raises(FakeClientError):
        storage.read_parquet("prices")


# ---------------------------------------------------------------------------
# write_json / read_json
# ---------------------------------------------------------------------------


def test_json_roundtrip(storage: Any, mock_client: MagicMock) -> None:
    """write_json followed by read_json reproduces the original dict."""
    data = _make_json()

    storage.write_json("meta", data)

    # Capture the bytes that were uploaded
    call_args = mock_client.put_object.call_args
    body_bytes: bytes = call_args.kwargs["Body"]

    mock_body = MagicMock()
    mock_body.read.return_value = body_bytes
    mock_client.get_object.return_value = {"Body": mock_body}

    result = storage.read_json("meta")

    assert result == data


def test_write_json_calls_put_object(storage: Any, mock_client: MagicMock) -> None:
    """write_json calls put_object with the correct bucket and key."""
    storage.write_json("meta", _make_json())

    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"] == "meta.json"
    assert isinstance(call_kwargs["Body"], bytes)


def test_read_json_missing_key_raises(storage: Any, mock_client: MagicMock) -> None:
    """`read_json` raises FileNotFoundError when the S3 object does not exist."""
    mock_client.get_object.side_effect = FakeClientError("NoSuchKey")

    with pytest.raises(FileNotFoundError, match="meta.json"):
        storage.read_json("meta")


def test_read_json_other_client_error_reraises(storage: Any, mock_client: MagicMock) -> None:
    """`read_json` re-raises ClientError when it is not a NoSuchKey error."""
    mock_client.get_object.side_effect = FakeClientError("AccessDenied")

    with pytest.raises(FakeClientError):
        storage.read_json("meta")


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


def test_exists_returns_true_for_parquet(storage: Any, mock_client: MagicMock) -> None:
    """`exists` returns True when the .parquet object exists."""
    # head_object succeeds for parquet key (first call), don't need second call
    mock_client.head_object.return_value = {}

    assert storage.exists("prices") is True


def test_exists_returns_true_for_json(storage: Any, mock_client: MagicMock) -> None:
    """`exists` returns True when only the .json object exists."""
    # First call (parquet) raises 404, second call (json) succeeds
    mock_client.head_object.side_effect = [FakeClientError("404"), {}]

    assert storage.exists("prices") is True


def test_exists_returns_false_when_neither_exists(storage: Any, mock_client: MagicMock) -> None:
    """`exists` returns False when neither .parquet nor .json objects exist."""
    mock_client.head_object.side_effect = FakeClientError("404")

    assert storage.exists("prices") is False


def test_exists_reraises_non_404_error(storage: Any, mock_client: MagicMock) -> None:
    """`exists` re-raises ClientError when it is not a 404 error."""
    mock_client.head_object.side_effect = FakeClientError("AccessDenied")

    with pytest.raises(FakeClientError):
        storage.exists("prices")


# ---------------------------------------------------------------------------
# boto3 not installed
# ---------------------------------------------------------------------------


def test_s3_storage_import_error_when_boto3_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3Storage raises ImportError with a helpful message when boto3 is missing."""
    monkeypatch.delitem(sys.modules, "trading_advisor.storage.s3", raising=False)

    # Remove boto3 so the import inside __init__ fails
    original_boto3 = sys.modules.pop("boto3", None)
    try:
        from trading_advisor.storage.s3 import S3Storage  # noqa: PLC0415

        with pytest.raises(ImportError, match="pip install wealthops"):
            S3Storage(bucket="test-bucket")
    finally:
        if original_boto3 is not None:
            sys.modules["boto3"] = original_boto3


# ---------------------------------------------------------------------------
# StorageBackend ABC compliance
# ---------------------------------------------------------------------------


def test_s3_storage_is_storage_backend(_patch_boto3: None) -> None:
    """S3Storage is a concrete subclass of StorageBackend."""
    from trading_advisor.storage.base import StorageBackend  # noqa: PLC0415
    from trading_advisor.storage.s3 import S3Storage  # noqa: PLC0415

    assert issubclass(S3Storage, StorageBackend)
