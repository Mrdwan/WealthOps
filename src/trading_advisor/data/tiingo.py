"""Tiingo API data provider — XAU/USD and forex daily OHLCV."""

from __future__ import annotations

import pandas as pd
import requests

from trading_advisor.data.base import OHLCVProvider

_BASE_URL = "https://api.tiingo.com/tiingo/fx/{ticker}/prices"
_OHLCV_COLUMNS = ["open", "high", "low", "close"]


class TiingoProvider(OHLCVProvider):
    """Fetches daily OHLCV from the Tiingo Forex API.

    Args:
        api_key: Tiingo API token used for authentication.
        session: Optional ``requests.Session`` for dependency injection and
            testing. If ``None``, a new session is created automatically.
    """

    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._session: requests.Session = session if session is not None else requests.Session()

    def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch daily OHLCV data for a forex symbol from the Tiingo API.

        Args:
            symbol: Ticker symbol, e.g. ``'XAUUSD'`` or ``'EURUSD'``.
                The symbol is lowercased before use in the URL.
            start: Start date in ``'YYYY-MM-DD'`` format.
            end: End date in ``'YYYY-MM-DD'`` format.

        Returns:
            DataFrame with a DatetimeIndex named ``date`` and columns
            ``open``, ``high``, ``low``, ``close``, sorted ascending by date.
            Returns an empty DataFrame (correct columns and DatetimeIndex) when
            the API returns an empty array.

        Raises:
            RuntimeError: If the API returns a non-200 HTTP status code.
        """
        ticker = symbol.lower()
        url = _BASE_URL.format(ticker=ticker)
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
        }
        params = {
            "startDate": start,
            "endDate": end,
            "resampleFreq": "1day",
        }

        response = self._session.get(url, headers=headers, params=params)

        if response.status_code != 200:
            snippet = response.text[:200]
            raise RuntimeError(f"Tiingo API returned {response.status_code}: {snippet}")

        data: list[dict[str, object]] = response.json()

        if not data:
            empty_index = pd.DatetimeIndex([], name="date")
            return pd.DataFrame(columns=_OHLCV_COLUMNS, index=empty_index)

        df = pd.DataFrame(data)
        df.columns = pd.Index([str(c).lower() for c in df.columns])
        df = df[_OHLCV_COLUMNS + ["date"]]
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
        df = df.set_index("date")
        df.index.name = "date"
        df = df.sort_index()
        return df
