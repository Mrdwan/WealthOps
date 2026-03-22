---
paths:
  - "src/trading_advisor/backtest/**"
  - "src/trading_advisor/strategy/**"
  - "src/trading_advisor/indicators/**"
---

- PREVENT LOOKAHEAD BIAS: All signals must use prior day's close. Never use today's close to decide today's action.
- Backtest and live runner share the same strategy code. The strategy module never knows whether it's running in backtest or live mode.
- Drawdown throttling must be active during backtest — it's part of the strategy.
- Cost model must include IG spread (0.3pts), slippage (0.1pts), and overnight funding.
