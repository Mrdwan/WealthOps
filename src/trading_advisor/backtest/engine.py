"""Backtest engine: simulates trap order execution with realistic costs.

Execution model:
  - Signal fires at EOD (23:00 UTC)
  - Trap order placed for next session (buy stop + limit)
  - If gap-through (high > limit) → NOT filled
  - Stop loss, take profit, trailing stop (Chandelier) on daily close
  - Time stop: 10 trading days
  - Costs: IG spread 0.3pts, slippage 0.1pts, overnight funding

Implemented in Task 1E.
"""
