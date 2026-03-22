"""Statistical validation: walk-forward, Monte Carlo bootstrap, shuffled-price test.

Tests:
  - Walk-forward efficiency: in-sample vs out-of-sample performance ratio > 50%
  - Monte Carlo: 10,000 resamples, 5th percentile positive
  - Shuffled-price: strategy fails on random data (p < 0.01)
  - t-statistic: mean_return × √N / std_return > 2.0

Implemented in Task 1F.
"""
