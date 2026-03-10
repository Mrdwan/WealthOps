"""Momentum Composite calculation: 5 components, z-scored, weighted sum.

Components (XAU/USD, no volume):
  - Momentum (6M return, skip last month): 44%
  - Trend (price vs 50/200 DMA): 22%
  - RSI (distance from extremes): 17%
  - ATR volatility (percentile rank): 11%
  - Support/Resistance (price clustering): 6%

Signal classification:
  STRONG_BUY  = composite > 2.0σ
  BUY         = composite > 1.5σ
  NEUTRAL     = between -1.5σ and 1.5σ
  SELL        = composite < -1.5σ

Implemented in Task 1B.
"""

from __future__ import annotations
