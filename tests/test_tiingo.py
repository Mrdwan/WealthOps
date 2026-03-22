"""Tests for TiingoProvider."""

import json
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from trading_advisor.data.tiingo import TiingoProvider

CANNED_RESPONSE: list[dict[str, Any]] = [
    {
        "date": "2024-01-02T00:00:00+00:00",
        "close": 2062.49,
        "high": 2078.53,
        "low": 2058.37,
        "open": 2065.99,
    },
    {
        "date": "2024-01-03T00:00:00+00:00",
        "close": 2042.47,
        "high": 2064.37,
        "low": 2039.35,
        "open": 2060.53,
    },
]


@pytest.fixture()
def mock_session(mocker: MockerFixture) -> MagicMock:
    """Return a mock requests.Session with a canned 200 response."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = CANNED_RESPONSE
    response.text = json.dumps(CANNED_RESPONSE)
    session.get.return_value = response
    return session


@pytest.fixture()
def provider(mock_session: MagicMock) -> TiingoProvider:
    """Return a TiingoProvider wired with the mock session."""
    return TiingoProvider(api_key="test-api-key", session=mock_session)


def test_fetch_returns_correct_shape(provider: TiingoProvider, mock_session: MagicMock) -> None:
    """Successful fetch returns DataFrame with 2 rows and 4 columns."""
    df = provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    assert df.shape == (2, 4)


def test_fetch_columns(provider: TiingoProvider, mock_session: MagicMock) -> None:
    """DataFrame columns are open, high, low, close."""
    df = provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    assert list(df.columns) == ["open", "high", "low", "close"]


def test_fetch_index_is_datetimeindex(provider: TiingoProvider, mock_session: MagicMock) -> None:
    """Index is a DatetimeIndex named 'date'."""
    df = provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "date"


def test_fetch_correct_url(provider: TiingoProvider, mock_session: MagicMock) -> None:
    """Correct URL constructed with lowercase symbol."""
    provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    call_args = mock_session.get.call_args
    url = call_args[0][0]
    assert url == "https://api.tiingo.com/tiingo/fx/xauusd/prices"


def test_fetch_correct_headers(provider: TiingoProvider, mock_session: MagicMock) -> None:
    """Correct Authorization header sent."""
    provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    call_args = mock_session.get.call_args
    headers = call_args[1]["headers"]
    assert headers["Authorization"] == "Token test-api-key"
    assert headers["Content-Type"] == "application/json"


def test_fetch_correct_params(provider: TiingoProvider, mock_session: MagicMock) -> None:
    """Correct query params sent: startDate, endDate, resampleFreq."""
    provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    call_args = mock_session.get.call_args
    params = call_args[1]["params"]
    assert params["startDate"] == "2024-01-02"
    assert params["endDate"] == "2024-01-03"
    assert params["resampleFreq"] == "1day"


def test_non_200_raises_runtime_error(mock_session: MagicMock) -> None:
    """Non-200 response raises RuntimeError with status code."""
    response = MagicMock()
    response.status_code = 403
    response.text = "Forbidden: invalid API key"
    mock_session.get.return_value = response
    provider = TiingoProvider(api_key="bad-key", session=mock_session)
    with pytest.raises(RuntimeError, match="403"):
        provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")


def test_empty_response_returns_empty_dataframe(mock_session: MagicMock) -> None:
    """Empty JSON array returns empty DataFrame with correct columns and DatetimeIndex."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = []
    mock_session.get.return_value = response
    provider = TiingoProvider(api_key="test-api-key", session=mock_session)
    df = provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    assert df.empty
    assert list(df.columns) == ["open", "high", "low", "close"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "date"


def test_data_values_match_canned_response(
    provider: TiingoProvider, mock_session: MagicMock
) -> None:
    """Data values match canned response fixture."""
    df = provider.fetch_ohlcv("XAUUSD", "2024-01-02", "2024-01-03")
    assert df.iloc[0]["open"] == pytest.approx(2065.99)
    assert df.iloc[0]["high"] == pytest.approx(2078.53)
    assert df.iloc[0]["low"] == pytest.approx(2058.37)
    assert df.iloc[0]["close"] == pytest.approx(2062.49)
    assert df.iloc[1]["open"] == pytest.approx(2060.53)
    assert df.iloc[1]["close"] == pytest.approx(2042.47)


def test_no_session_creates_default_session() -> None:
    """TiingoProvider with no session creates its own requests.Session."""
    import requests

    provider = TiingoProvider(api_key="test-key")
    assert isinstance(provider._session, requests.Session)


def test_eurusd_symbol_lowercased(provider: TiingoProvider, mock_session: MagicMock) -> None:
    """EURUSD symbol is lowercased in the URL."""
    provider.fetch_ohlcv("EURUSD", "2024-01-02", "2024-01-03")
    call_args = mock_session.get.call_args
    url = call_args[0][0]
    assert url == "https://api.tiingo.com/tiingo/fx/eurusd/prices"
