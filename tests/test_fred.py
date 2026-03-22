"""Tests for FredProvider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from trading_advisor.data.fred import FredProvider

CANNED_SERIES: pd.Series = pd.Series(  # type: ignore[type-arg]
    [20.5, 21.3, float("nan"), 19.8],
    index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
    name="value",
)


@pytest.fixture()
def mock_fred_client() -> MagicMock:
    """Return a mock fredapi.Fred client with a canned get_series response."""
    client = MagicMock()
    client.get_series.return_value = CANNED_SERIES
    return client


@pytest.fixture()
def provider(mock_fred_client: MagicMock) -> FredProvider:
    """Return a FredProvider wired with the mock fred client."""
    return FredProvider(api_key="test-api-key", fred_client=mock_fred_client)


def test_fetch_returns_dataframe_with_value_column(
    provider: FredProvider, mock_fred_client: MagicMock
) -> None:
    """Successful fetch returns DataFrame with a 'value' column."""
    df = provider.fetch_series("VIXCLS", "2024-01-02", "2024-01-05")
    assert "value" in df.columns


def test_fetch_index_is_datetimeindex_named_date(
    provider: FredProvider, mock_fred_client: MagicMock
) -> None:
    """Index is a DatetimeIndex named 'date'."""
    df = provider.fetch_series("VIXCLS", "2024-01-02", "2024-01-05")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "date"


def test_nan_rows_are_dropped(provider: FredProvider, mock_fred_client: MagicMock) -> None:
    """NaN rows are dropped — 3 valid rows from 4 input rows."""
    df = provider.fetch_series("VIXCLS", "2024-01-02", "2024-01-05")
    assert len(df) == 3


def test_data_values_match_canned_response(
    provider: FredProvider, mock_fred_client: MagicMock
) -> None:
    """Data values match canned series fixture."""
    df = provider.fetch_series("VIXCLS", "2024-01-02", "2024-01-05")
    assert df.iloc[0]["value"] == pytest.approx(20.5)
    assert df.iloc[1]["value"] == pytest.approx(21.3)
    assert df.iloc[2]["value"] == pytest.approx(19.8)


def test_fredapi_error_wrapped_in_runtime_error(
    mock_fred_client: MagicMock,
) -> None:
    """fredapi ValueError is wrapped in RuntimeError with descriptive message."""
    mock_fred_client.get_series.side_effect = ValueError("FRED API error")
    provider = FredProvider(api_key="test-api-key", fred_client=mock_fred_client)
    with pytest.raises(RuntimeError, match="VIXCLS"):
        provider.fetch_series("VIXCLS", "2024-01-02", "2024-01-05")


def test_fredapi_requests_error_wrapped_in_runtime_error(
    mock_fred_client: MagicMock,
) -> None:
    """fredapi requests.RequestException is wrapped in RuntimeError."""
    import requests

    mock_fred_client.get_series.side_effect = requests.exceptions.RequestException(
        "connection error"
    )
    provider = FredProvider(api_key="test-api-key", fred_client=mock_fred_client)
    with pytest.raises(RuntimeError, match="VIXCLS"):
        provider.fetch_series("VIXCLS", "2024-01-02", "2024-01-05")


def test_empty_series_returns_empty_dataframe_with_correct_schema(
    mock_fred_client: MagicMock,
) -> None:
    """All-NaN series returns empty DataFrame with 'value' column and DatetimeIndex named 'date'."""
    mock_fred_client.get_series.return_value = pd.Series(
        [float("nan"), float("nan")],
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        name="value",
    )
    provider = FredProvider(api_key="test-api-key", fred_client=mock_fred_client)
    df = provider.fetch_series("VIXCLS", "2024-01-02", "2024-01-03")
    assert df.empty
    assert "value" in df.columns
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "date"


def test_default_fred_client_created_when_none(mocker: MockerFixture) -> None:
    """FredProvider with no fred_client creates its own fredapi.Fred instance."""
    mock_fred_class = mocker.patch("trading_advisor.data.fred.Fred")
    mock_fred_class.return_value = MagicMock()
    provider = FredProvider(api_key="real-api-key")
    mock_fred_class.assert_called_once_with(api_key="real-api-key")
    assert provider._fred is mock_fred_class.return_value


def test_correct_args_passed_to_fredapi(
    provider: FredProvider, mock_fred_client: MagicMock
) -> None:
    """Correct series_id, observation_start, observation_end passed to fredapi."""
    provider.fetch_series("T10Y2Y", "2024-01-02", "2024-01-05")
    mock_fred_client.get_series.assert_called_once_with(
        "T10Y2Y",
        observation_start="2024-01-02",
        observation_end="2024-01-05",
    )
