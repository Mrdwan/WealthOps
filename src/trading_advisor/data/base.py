"""Abstract base classes for market data and macro data providers."""

from abc import ABC, abstractmethod

import pandas as pd


class OHLCVProvider(ABC):
    """Abstract base class for all OHLCV data providers.

    Implementors must return a DataFrame with a DatetimeIndex named ``date``
    and columns ``open``, ``high``, ``low``, ``close``. The ``volume`` column
    is optional (use 0.0 for forex instruments that do not report volume).
    """

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol between start and end dates.

        Args:
            symbol: Ticker symbol, e.g. ``'XAUUSD'``.
            start: Start date in ``'YYYY-MM-DD'`` format.
            end: End date in ``'YYYY-MM-DD'`` format.

        Returns:
            DataFrame with a DatetimeIndex named ``date`` and columns
            ``open``, ``high``, ``low``, ``close``. ``volume`` is optional
            (0.0 for forex).
        """
        ...


class MacroProvider(ABC):
    """Abstract base class for macro data providers.

    Implementors must return a DataFrame with a DatetimeIndex named ``date``
    and a single ``value`` column.
    """

    @abstractmethod
    def fetch_series(self, series_id: str, start: str, end: str) -> pd.DataFrame:
        """Fetch a macro data series between start and end dates.

        Args:
            series_id: Series identifier, e.g. ``'VIXCLS'``, ``'T10Y2Y'``,
                ``'FEDFUNDS'``.
            start: Start date in ``'YYYY-MM-DD'`` format.
            end: End date in ``'YYYY-MM-DD'`` format.

        Returns:
            DataFrame with a DatetimeIndex named ``date`` and a single
            ``value`` column. NaN rows are excluded.
        """
        ...
