"""Data providers package."""

from trading_advisor.data.base import MacroProvider, OHLCVProvider
from trading_advisor.data.fred import FredProvider
from trading_advisor.data.ingest import DataIngestor
from trading_advisor.data.tiingo import TiingoProvider
from trading_advisor.data.validation import ValidationResult, validate_ohlcv

__all__ = [
    "OHLCVProvider",
    "MacroProvider",
    "TiingoProvider",
    "FredProvider",
    "validate_ohlcv",
    "ValidationResult",
    "DataIngestor",
]
