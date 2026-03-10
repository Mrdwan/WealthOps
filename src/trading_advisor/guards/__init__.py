"""Guards package: 5 hard pass/fail safety gates.

Guards 1–5:
  1. MacroGate     — DXY < 200 SMA (weak dollar favors gold)
  2. TrendGate     — ADX(14) > 20 (trending market)
  3. EventGuard    — no FOMC/NFP/CPI within 2 days
  4. PullbackZone  — close within 2% of EMA_8
  5. DrawdownGate  — portfolio drawdown < 15%

All must pass. Any fail = no signal.
"""
