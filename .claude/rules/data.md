---
paths:
  - "src/trading_advisor/data/**"
  - "src/trading_advisor/storage/**"
---

- All I/O goes through `StorageBackend` ABC. Never read/write files directly.
- OHLCV validation: high >= low, high >= open, high >= close, low <= open, low <= close, no nulls, no duplicate timestamps, price within 5% of previous close.
