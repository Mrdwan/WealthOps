"""Dual-constraint position sizing for XAU/USD.

Sizing = min(ATR-based, Cap-based):
  ATR-based:  (Portfolio × risk_pct) / (ATR_14 × 2)
  Cap-based:  Portfolio × 0.15 / Entry_Price

Risk % scales with capital:
  < €5,000    → 1.0%
  €5k–€15k   → 1.5%
  >= €15,000  → 2.0%

Implemented in Task 1D.
"""
