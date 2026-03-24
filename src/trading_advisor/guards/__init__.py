"""Guards package: 5 hard pass/fail safety gates.

Guards 1–5:
  1. MacroGate     — EUR/USD close > EUR/USD 200 SMA (weak dollar favors gold)
  2. TrendGate     — ADX(14) > 20 (trending market)
  3. EventGuard    — no FOMC/NFP/CPI within 2 days
  4. PullbackZone  — close within 2% of EMA_8
  5. DrawdownGate  — portfolio drawdown < 15%

All must pass. Any fail = no signal.
"""

from trading_advisor.guards.base import Guard, GuardResult
from trading_advisor.guards.drawdown_gate import DrawdownGate
from trading_advisor.guards.event_guard import EventGuard, load_calendar
from trading_advisor.guards.macro_gate import MacroGate
from trading_advisor.guards.pipeline import run_guards
from trading_advisor.guards.pullback_zone import PullbackZone
from trading_advisor.guards.trend_gate import TrendGate

__all__ = [
    "DrawdownGate",
    "EventGuard",
    "Guard",
    "GuardResult",
    "MacroGate",
    "PullbackZone",
    "TrendGate",
    "load_calendar",
    "run_guards",
]
