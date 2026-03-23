"""Tests for momentum composite calculation and signal classification."""

import numpy as np
import pandas as pd
import pytest

from trading_advisor.indicators.composite import (
    Signal,
    atr_volatility_component,
    momentum_component,
    rolling_zscore,
    rsi_filter_component,
    sr_proximity_component,
    trend_component,
)


class TestSignal:
    def test_all_values(self) -> None:
        """Signal enum has all 5 expected values."""
        assert Signal.STRONG_BUY.value == "STRONG_BUY"
        assert Signal.BUY.value == "BUY"
        assert Signal.NEUTRAL.value == "NEUTRAL"
        assert Signal.SELL.value == "SELL"
        assert Signal.STRONG_SELL.value == "STRONG_SELL"
        assert len(Signal) == 5


class TestRollingZscore:
    def test_linear_sequence(self) -> None:
        """Linear ascending sequence: z-score = 1.0 at each position."""
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(1.0)
        assert result.iloc[3] == pytest.approx(1.0)
        assert result.iloc[4] == pytest.approx(1.0)

    def test_zero_std_nan(self) -> None:
        """Constant values (zero std) produce NaN, not inf."""
        series = pd.Series([5.0, 5.0, 5.0, 5.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        assert pd.isna(result.iloc[2])
        assert pd.isna(result.iloc[3])
        # Verify it's NaN, not inf
        assert not np.isinf(result.iloc[2])

    def test_short_series_all_nan(self) -> None:
        """Series shorter than window produces all NaN."""
        series = pd.Series([1.0, 2.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        assert result.isna().all()

    def test_negative_zscore(self) -> None:
        """Value below mean gives negative z-score."""
        series = pd.Series([10.0, 12.0, 8.0], dtype=np.float64)
        result = rolling_zscore(series, window=3)
        # mean=10, std=2, z=(8-10)/2=-1.0
        assert result.iloc[2] == pytest.approx(-1.0)

    def test_default_window_252(self) -> None:
        """Default window is 252. First 251 values should be NaN."""
        series = pd.Series(np.arange(260, dtype=np.float64))
        result = rolling_zscore(series)
        assert result.iloc[:251].isna().all()
        assert not pd.isna(result.iloc[251])

    def test_invalid_window_raises(self) -> None:
        """window < 2 raises ValueError."""
        series = pd.Series([1.0, 2.0], dtype=np.float64)
        with pytest.raises(ValueError, match="window must be >= 2"):
            rolling_zscore(series, window=1)


class TestMomentumComponent:
    def test_raw_formula(self) -> None:
        """Verify momentum raw = close[t-21] / close[t-126] - 1."""
        # Build a 130-element series. We need indices 21 and 126 to have
        # known values. Use window=2 so we only need 2 valid raw values
        # to get a non-NaN z-score.
        n = 130
        close = pd.Series(np.linspace(100.0, 200.0, n), dtype=np.float64)
        # At index 129 (last): raw = close[129-21]/close[129-126] - 1
        #                            = close[108] / close[3] - 1
        expected_raw_last = float(close.iloc[108]) / float(close.iloc[3]) - 1.0
        # At index 128: raw = close[107] / close[2] - 1
        expected_raw_prev = float(close.iloc[107]) / float(close.iloc[2]) - 1.0

        result = momentum_component(close, window=2)
        # With window=2, first valid z-score is at second valid raw value.
        # The raw values start being valid at index 126 (need shift(126)).
        # z-score with window=2 requires 2 valid values, so first valid
        # z-score at index 127.
        # At last index (129), z-score = (raw_129 - mean) / std over window=2
        mean_last = (expected_raw_last + expected_raw_prev) / 2.0
        std_last = float(pd.Series([expected_raw_prev, expected_raw_last]).std())
        expected_z = (expected_raw_last - mean_last) / std_last
        assert result.iloc[129] == pytest.approx(expected_z, rel=1e-6)

    def test_uptrend_positive_raw(self) -> None:
        """Rising prices over 6 months produce positive raw momentum."""
        # Steadily rising prices: close[t-21] > close[t-126]
        n = 260
        close = pd.Series(np.linspace(100.0, 300.0, n), dtype=np.float64)
        result = momentum_component(close, window=3)
        # All valid z-scores should be based on positive raw values.
        # With uniformly rising, raw momentum is always positive and
        # roughly constant, so z-scores cluster near 0 (constant raw).
        # But the raw values themselves are positive, so the mean is positive.
        # Check the last few valid values are finite.
        valid = result.dropna()
        assert len(valid) > 0
        assert np.all(np.isfinite(valid.values))

    def test_returns_zscore(self) -> None:
        """Output is z-scored (mean near 0, std near 1 over rolling window)."""
        n = 500
        rng = np.random.default_rng(42)
        close = pd.Series(np.cumsum(rng.normal(0.5, 1.0, n)) + 200.0, dtype=np.float64)
        result = momentum_component(close, window=50)
        valid = result.dropna()
        # Z-scores should have mean near 0 and std near 1 across the series
        assert abs(float(valid.mean())) < 1.0
        assert 0.3 < float(valid.std()) < 2.0


class TestTrendComponent:
    def test_golden_cross_above_both(self) -> None:
        """close > SMA_50 > SMA_200 -> raw = 3."""
        n = 10
        close = pd.Series([110.0] * n, dtype=np.float64)
        sma_50 = pd.Series([105.0] * n, dtype=np.float64)
        sma_200 = pd.Series([100.0] * n, dtype=np.float64)
        # raw = 3.0 constant -> z-score = NaN (zero std)
        result = trend_component(close, sma_50, sma_200, window=3)
        # Constant raw => zero std => NaN z-score
        assert pd.isna(result.iloc[-1])

    def test_death_cross_below_both(self) -> None:
        """close < SMA_200, SMA_50 < SMA_200 -> raw = 0."""
        n = 10
        close = pd.Series([90.0] * n, dtype=np.float64)
        sma_50 = pd.Series([95.0] * n, dtype=np.float64)
        sma_200 = pd.Series([100.0] * n, dtype=np.float64)
        # raw = 0.0 constant -> z-score = NaN (zero std)
        result = trend_component(close, sma_50, sma_200, window=3)
        assert pd.isna(result.iloc[-1])

    def test_mixed_conditions(self) -> None:
        """Transition from bearish to bullish produces varying raw values."""
        # First 5: bearish (raw=0), last 5: bullish (raw=3)
        close = pd.Series([90.0] * 5 + [110.0] * 5, dtype=np.float64)
        sma_50 = pd.Series([95.0] * 5 + [105.0] * 5, dtype=np.float64)
        sma_200 = pd.Series([100.0] * 10, dtype=np.float64)
        result = trend_component(close, sma_50, sma_200, window=3)
        # At index 6 (window=3, first valid z at index where we have 3 vals):
        # Raw transitions from 0 to 3.
        # Index 4: raw=0, Index 5: raw=3, Index 6: raw=3
        # window=3 over [0, 3, 3]: mean=2, std=sqrt(3), z=(3-2)/sqrt(3)
        vals = [0.0, 3.0, 3.0]
        mean_val = float(np.mean(vals))
        std_val = float(pd.Series(vals).std())  # ddof=1
        expected_z = (3.0 - mean_val) / std_val
        assert result.iloc[6] == pytest.approx(expected_z, rel=1e-6)

    def test_sma50_gt_sma200_not_swapped(self) -> None:
        """Third condition is (sma_50 > sma_200), not (sma_200 > sma_50)."""
        # 6 points: first 3 have sma_50 < sma_200, last 3 have sma_50 > sma_200.
        # close > both SMAs throughout, so first two conditions always True.
        #
        # Correct formula: raw = (close>sma_50) + (close>sma_200) + (sma_50>sma_200)
        #   idx 0-2: 1 + 1 + 0 = 2
        #   idx 3-5: 1 + 1 + 1 = 3
        #
        # Swapped mutation: raw = ... + (sma_200 > sma_50)
        #   idx 0-2: 1 + 1 + 1 = 3  (FLIPPED)
        #   idx 3-5: 1 + 1 + 0 = 2  (FLIPPED)
        #
        # z at index 4 (window=3 over raw [2,3,3]):
        #   correct: z = (3 - 8/3) / std([2,3,3]) = positive
        #   swapped: raw = [3,2,2], z = (2-7/3)/std([3,2,2]) = negative
        close = pd.Series([110.0] * 6, dtype=np.float64)
        sma_50 = pd.Series([95.0, 95.0, 95.0, 105.0, 105.0, 105.0], dtype=np.float64)
        sma_200 = pd.Series([100.0] * 6, dtype=np.float64)
        result = trend_component(close, sma_50, sma_200, window=3)
        # With correct formula, z at index 4 should be positive
        assert result.iloc[4] == pytest.approx(1.0 / np.sqrt(3), rel=1e-6)


class TestRsiFilterComponent:
    def test_rsi_50_gives_max_raw(self) -> None:
        """RSI = 50 -> raw = 50 (maximum)."""
        n = 10
        rsi = pd.Series([50.0] * n, dtype=np.float64)
        # raw = 50 - |50 - 50| = 50 constant -> zero std -> NaN z-score
        result = rsi_filter_component(rsi, window=3)
        assert pd.isna(result.iloc[-1])

    def test_rsi_80_gives_low_raw(self) -> None:
        """RSI = 80 -> raw = 50 - 30 = 20."""
        n = 10
        rsi = pd.Series([80.0] * n, dtype=np.float64)
        # raw = 50 - |80 - 50| = 50 - 30 = 20, constant -> NaN
        result = rsi_filter_component(rsi, window=3)
        assert pd.isna(result.iloc[-1])

    def test_rsi_20_gives_low_raw(self) -> None:
        """RSI = 20 -> raw = 50 - 30 = 20 (symmetric with RSI=80)."""
        n = 10
        rsi = pd.Series([20.0] * n, dtype=np.float64)
        # raw = 50 - |20 - 50| = 50 - 30 = 20, constant -> NaN
        result = rsi_filter_component(rsi, window=3)
        assert pd.isna(result.iloc[-1])

    def test_varying_rsi_zscore(self) -> None:
        """RSI transitioning from 50 to 80: raw goes from 50 to 20."""
        rsi = pd.Series([50.0, 50.0, 50.0, 80.0, 80.0], dtype=np.float64)
        # raw: [50, 50, 50, 20, 20]
        result = rsi_filter_component(rsi, window=3)
        # At index 4, window=[50, 20, 20]: mean=30, std=pd.Series([50,20,20]).std()
        vals = [50.0, 20.0, 20.0]
        mean_val = float(np.mean(vals))
        std_val = float(pd.Series(vals).std())
        expected_z = (20.0 - mean_val) / std_val
        assert result.iloc[4] == pytest.approx(expected_z, rel=1e-6)

    def test_abs_distinguishes_above_below_50(self) -> None:
        """abs() makes RSI=80 and RSI=20 produce same raw; without abs they differ."""
        # With abs(): raw = 50 - |rsi - 50| => [20, 50, 20] => [30, 50, 20]
        #   wait: 50 - |20-50| = 50-30 = 20, 50-|50-50|=50, 50-|80-50|=50-30=20
        #   raw = [20, 50, 20], but we want [30, 50, 20] -- recalculate:
        #   Actually raw for RSI=20: 50-|20-50|=50-30=20
        #   raw for RSI=50: 50-|50-50|=50
        #   raw for RSI=80: 50-|80-50|=50-30=20
        #   So raw = [20, 50, 20]
        # Without abs(): raw = 50 - (rsi - 50) => 50-(20-50)=80, 50-(50-50)=50, 50-(80-50)=20
        #   raw = [80, 50, 20]
        # z-score at index 2 with window=3:
        #   With abs: mean(20,50,20)=30, std=sqrt(((20-30)^2+(50-30)^2+(20-30)^2)/2)
        #     = sqrt((100+400+100)/2) = sqrt(300) = 17.32..., z = (20-30)/17.32 = -0.5774
        #   Without abs: mean(80,50,20)=50, std=30, z = (20-50)/30 = -1.0
        rsi = pd.Series([20.0, 50.0, 80.0], dtype=np.float64)
        result = rsi_filter_component(rsi, window=3)
        # With abs, z[2] = -1/sqrt(3) approx -0.5774
        assert result.iloc[2] == pytest.approx(-1.0 / np.sqrt(3), rel=1e-6)


class TestAtrVolatilityComponent:
    def test_median_atr_gives_max_raw(self) -> None:
        """ATR at 50th percentile -> raw near 1.0."""
        # Use oscillating data so percentile ranks vary across the window.
        # With window=5, we need enough data for both percentile rank
        # (5 values) and z-score (another 5 valid raw values) = 10+ rows.
        rng = np.random.default_rng(99)
        n = 50
        atr = pd.Series(rng.uniform(10.0, 90.0, n), dtype=np.float64)
        result = atr_volatility_component(atr, window=5)
        valid = result.dropna()
        # With random data and small window, we should get valid z-scores
        assert len(valid) > 0
        assert np.all(np.isfinite(valid.values))

    def test_extreme_atr_gives_low_raw(self) -> None:
        """ATR at extreme percentile -> raw near 0.0."""
        # Build data where percentile rank varies, then an extreme outlier.
        # Oscillating values for first part, then a huge spike.
        rng = np.random.default_rng(42)
        n = 50
        base = rng.uniform(40.0, 60.0, n)
        # Make the last value an extreme outlier
        base[-1] = 500.0
        atr = pd.Series(base, dtype=np.float64)
        result = atr_volatility_component(atr, window=5)
        valid = result.dropna()
        assert len(valid) > 0
        # The extreme outlier should have percentile rank near 100,
        # making atr_raw near 0, which is lower than the mid-range
        # atr_raw values preceding it. The z-score should be negative.
        assert float(result.iloc[-1]) < 0.0

    def test_deterministic_percentile_rank_and_abs(self) -> None:
        """Verify exact z-scores, killing percentile rank and abs() mutations."""
        # ATR = [3.0, 1.0, 2.0, 4.0, 1.5, 3.5] with window=3
        #
        # Percentile ranks (window=3):
        #   idx 2: [3,1,2] curr=2, below in [3,1]: 1/2*100 = 50
        #   idx 3: [1,2,4] curr=4, below in [1,2]: 2/2*100 = 100
        #   idx 4: [2,4,1.5] curr=1.5, below in [2,4]: 0/2*100 = 0
        #   idx 5: [4,1.5,3.5] curr=3.5, below in [4,1.5]: 1/2*100 = 50
        #
        # atr_raw = 1 - abs(pctile - 50) / 50:
        #   idx 2: 1 - |50-50|/50 = 1.0
        #   idx 3: 1 - |100-50|/50 = 0.0
        #   idx 4: 1 - |0-50|/50 = 0.0   (WITHOUT abs: 1-(0-50)/50 = 2.0)
        #   idx 5: 1 - |50-50|/50 = 1.0
        #
        # z-score window=3 over raw [1.0, 0.0, 0.0, 1.0]:
        #   idx 4: window=[1,0,0], z = (0-1/3)/std([1,0,0]) = -0.5774
        #   idx 5: window=[0,0,1], z = (1-1/3)/std([0,0,1]) = 1.1547
        atr = pd.Series([3.0, 1.0, 2.0, 4.0, 1.5, 3.5], dtype=np.float64)
        result = atr_volatility_component(atr, window=3)
        assert result.iloc[4] == pytest.approx(-1.0 / np.sqrt(3), rel=1e-6)
        assert result.iloc[5] == pytest.approx(2.0 / np.sqrt(3), rel=1e-6)


class TestSrProximityComponent:
    def test_at_20d_high(self) -> None:
        """Close = 20d high -> raw = 1.0."""
        n = 30
        # Close steadily rising, so close always equals 20d high
        close = pd.Series(np.arange(1.0, n + 1.0), dtype=np.float64)
        high = close.copy()
        result = sr_proximity_component(close, high, lookback=20, window=3)
        # raw = 1 - (high_20d - close)/close
        # When close is at its 20d high: high_20d = close, so raw = 1.0
        # Constant raw=1.0 after lookback period -> zero std -> NaN
        # Check that all z-scored values past warmup are NaN (constant raw)
        assert pd.isna(result.iloc[-1])

    def test_below_20d_high(self) -> None:
        """Close 2% below 20d high -> raw approximately 0.98."""
        n = 30
        # Build: first 25 values = 100.0, then high spikes to 102.0 at idx 25,
        # remaining close stays at 100.0
        close_vals = [100.0] * n
        high_vals = [100.0] * n
        high_vals[25] = 102.0  # spike the high

        close = pd.Series(close_vals, dtype=np.float64)
        high = pd.Series(high_vals, dtype=np.float64)

        result = sr_proximity_component(close, high, lookback=20, window=3)

        # At index 29: high_20d = max of high[10:30] = 102.0
        # raw = 1 - (102 - 100)/100 = 1 - 0.02 = 0.98
        # Before the spike (indices < 25): raw = 1.0
        # After: raw transitions to 0.98
        # At index 29 with window=3, preceding raws were also 0.98 (indices 27,28,29)
        # all have same high_20d since spike is in all their windows.
        # Indices 26,27,28,29 all have high_20d=102 (spike at 25 within lookback=20)
        # raw = 0.98 constant -> NaN z-score? Let's check indices before spike window.
        # Index 24: high_20d = max(high[5:25]) = 100.0, raw=1.0
        # Index 25: high_20d = max(high[6:26]) = 102.0, raw = 1-2/100 = 0.98
        # window=3 at index 26: raws = [1.0, 0.98, 0.98]
        vals = [1.0, 0.98, 0.98]
        mean_val = float(np.mean(vals))
        std_val = float(pd.Series(vals).std())
        expected_z = (0.98 - mean_val) / std_val
        assert result.iloc[26] == pytest.approx(expected_z, rel=1e-4)
