"""Verify technical indicators against TradingView.

Prints indicator values for 5 random dates in a side-by-side
table format for manual comparison.

Usage:
    uv run python scripts/verify_indicators.py
"""

from pathlib import Path

import pandas as pd

from trading_advisor.indicators.technical import compute_all_indicators
from trading_advisor.storage.local import LocalStorage


def main() -> None:
    """Print indicator values for manual TradingView comparison."""
    data_dir = Path("data")
    storage = LocalStorage(data_dir=data_dir)

    # Load data
    ohlcv = storage.read_parquet("ohlcv/XAUUSD_daily")
    eurusd = storage.read_parquet("ohlcv/EURUSD_daily")

    # Compute indicators
    result = compute_all_indicators(ohlcv, eurusd)

    # Pick 5 random dates after warmup (row 200+)
    valid = result.iloc[200:]
    sample = valid.sample(n=min(5, len(valid)), random_state=42)
    sample = sample.sort_index()

    # Print table
    indicators = ["rsi_14", "ema_8", "sma_200", "adx_14", "atr_14"]

    print("\n=== TradingView Verification: XAU/USD ===\n")
    print(f"{'Date':<14}", end="")
    for ind in indicators:
        print(f"{ind:>14}", end="")
    print()
    print("-" * (14 + 14 * len(indicators)))

    for date, row in sample.iterrows():
        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        print(f"{date_str:<14}", end="")
        for ind in indicators:
            val = row[ind]
            if pd.isna(val):
                print(f"{'NaN':>14}", end="")
            else:
                print(f"{val:>14.4f}", end="")
        print()

    print("\nCompare these values with TradingView XAU/USD daily chart.")
    print(f"Total rows: {len(result)}, after warmup: {len(valid)}")


if __name__ == "__main__":
    main()
