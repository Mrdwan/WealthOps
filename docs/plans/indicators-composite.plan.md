# Plan: Indicators & Composite (Task 1B)

## Goal

Implement all 14 technical indicators and the 5-component momentum composite score for XAU/USD. Technical indicators go in `indicators/technical.py`, composite logic in `indicators/composite.py`. Each function is pure (DataFrame/Series in → Series out), fully typed, and tested against hand-calculated values. The composite produces a weighted z-score and classifies signals as STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL.

## File Map

- `src/trading_advisor/indicators/technical.py` — all technical indicator functions (RSI, EMA, SMA, MACD, ADX, ATR, wick ratios, relative strength)
- `src/trading_advisor/indicators/composite.py` — rolling z-score utility, 5 composite component functions, assembly, Signal enum, classification
- `src/trading_advisor/indicators/__init__.py` — re-exports of public API
- `tests/test_indicators.py` — unit tests for all technical indicators
- `tests/test_composite.py` — unit tests for z-score, components, assembly, classification

## Function Signatures

### technical.py

```python
def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series
def compute_ema(series: pd.Series, span: int) -> pd.Series
def compute_ema_fan(ema_8: pd.Series, ema_20: pd.Series, ema_50: pd.Series) -> pd.Series  # bool Series
def compute_sma(series: pd.Series, window: int) -> pd.Series
def compute_macd_histogram(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series
def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame  # columns: plus_di, minus_di, adx
def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series
def compute_wick_ratios(df: pd.DataFrame) -> pd.DataFrame  # adds upper_wick_ratio, lower_wick_ratio columns
def compute_distance_from_20d_low(close: pd.Series, low: pd.Series, window: int = 20) -> pd.Series
def compute_relative_strength_vs_usd(xau_close: pd.Series, eurusd_close: pd.Series, window: int = 20) -> pd.Series
def compute_all_indicators(ohlcv: pd.DataFrame, eurusd: pd.DataFrame) -> pd.DataFrame
```

### composite.py

```python
class Signal(Enum): STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL

def rolling_zscore(series: pd.Series, window: int = 252) -> pd.Series
def momentum_component(close: pd.Series, window: int = 252) -> pd.Series  # returns z-scored
def trend_component(close: pd.Series, sma_50: pd.Series, sma_200: pd.Series, window: int = 252) -> pd.Series
def rsi_filter_component(rsi: pd.Series, window: int = 252) -> pd.Series
def atr_volatility_component(atr: pd.Series, window: int = 252) -> pd.Series
def sr_proximity_component(close: pd.Series, high: pd.Series, lookback: int = 20, window: int = 252) -> pd.Series
def compute_composite(indicators: pd.DataFrame) -> pd.DataFrame  # adds component columns + composite + signal
def classify_signal(composite: float) -> Signal
```

## Tasks

### Task 1: RSI(14) [1B.1]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Implement `compute_rsi` using Wilder's smoothing. First `period` gains/losses use SMA, then exponential smoothing: `avg = (prev_avg * (period-1) + current) / period`. Returns Series with NaN for first `period` rows. Also establish the module structure (imports, docstring, type annotations).
- **Test**: Hand-calculated RSI values for a 20-element close series. Test: warmup rows are NaN, steady uptrend → RSI > 50, steady downtrend → RSI < 50, flat prices → RSI = 50 (edge case: zero avg_loss → RSI = 100).
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: RSI matches hand-calculated values, mypy clean, all tests pass.
- [x] Completed

### Task 2: Moving Averages — EMAs + SMAs + EMA Fan [1B.2 + 1B.3]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Implement `compute_ema` (pandas ewm with span, adjust=False), `compute_sma` (rolling mean), `compute_ema_fan` (boolean: EMA_8 > EMA_20 > EMA_50). All return pd.Series. SMA returns NaN for first `window-1` rows. EMA starts from first value.
- **Test**: EMA_8 of 10 close prices (pre-computed). SMA_50 = mean of last 50 values (verify exactly). EMA fan True when aligned, False when crossed.
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: All MA tests pass, mypy clean.
- [x] Completed

### Task 3: MACD Histogram [1B.4]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Implement `compute_macd_histogram`. MACD line = EMA_12 - EMA_26. Signal line = 9-period EMA of MACD line. Histogram = MACD - Signal. Use `compute_ema` internally. Returns the histogram Series.
- **Test**: Pre-computed MACD histogram for a 30-element close series. Uptrend → positive histogram, downtrend → negative.
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: Histogram matches pre-computed values, mypy clean.
- [x] Completed

### Task 4: ADX(14) [1B.5]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: opus
- **Action**: Implement `compute_adx` returning DataFrame with columns `plus_di`, `minus_di`, `adx`. Steps: (1) +DM = high - prev_high if positive and > low change, else 0. -DM = prev_low - low if positive and > high change, else 0. (2) Smooth +DM, -DM, TR using Wilder's smoothing (first N use sum, then `prev * (N-1)/N + current`). (3) +DI = 100 * smoothed_+DM / smoothed_TR. (4) DX = 100 * |+DI - -DI| / (+DI + -DI). (5) ADX = Wilder's smoothed DX. First `2*period - 1` rows are NaN.
- **Test**: Flat price → ADX near 0. Strong trend → ADX > 25. Pre-computed +DI, -DI, ADX for a known dataset.
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: ADX matches known values, edge cases handled, mypy clean.
- [x] Completed

### Task 5: ATR(14) [1B.6]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Implement `compute_atr`. True Range = max(high-low, |high-prev_close|, |low-prev_close|). First ATR = SMA of first `period` TRs. Then Wilder's smoothing: `(prev_atr * (period-1) + current_tr) / period`. Returns Series, NaN for first `period` rows.
- **Test**: Pre-computed ATR for 20 rows of OHLC data. Volatile data → higher ATR. Flat data → ATR = high - low.
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: ATR matches hand-calculated values, mypy clean.
- [x] Completed

### Task 6: Wick Ratios + Distance from 20d Low [1B.7]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Implement `compute_wick_ratios` — upper: `(high - max(open,close)) / (high-low)`, lower: `(min(open,close) - low) / (high-low)`. Edge case: high == low → both = 0.0. Implement `compute_distance_from_20d_low` — `(close - rolling_min(low, 20)) / close`. NaN for first 19 rows.
- **Test**: Bullish candle (close > open) wick ratios. Bearish candle. Doji (open == close). High == low edge case. Distance: close at 20d low → 0.0, close above → positive.
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: All wick ratio and distance tests pass, edge cases covered, mypy clean.
- [x] Completed

### Task 7: Relative Strength vs USD [1B.8]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Implement `compute_relative_strength_vs_usd`. Ratio = `xau_close / eurusd_close`. Return rolling 20-day z-score of the ratio (use `(x - rolling_mean) / rolling_std`). NaN for first 19 rows.
- **Test**: Synthetic XAU and EUR/USD series. Rising ratio → positive z-score. Flat ratio → z-score near 0. Verify NaN handling.
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: Z-score matches pre-computed values, mypy clean.
- [x] Completed

### Task 8: Indicator Assembly [1B.9]
- **Files**: `src/trading_advisor/indicators/technical.py`, `src/trading_advisor/indicators/__init__.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Implement `compute_all_indicators(ohlcv, eurusd)` that calls all indicator functions and returns a single DataFrame with columns: `rsi_14`, `ema_8`, `ema_20`, `ema_50`, `ema_fan`, `sma_50`, `sma_200`, `macd_histogram`, `plus_di`, `minus_di`, `adx_14`, `atr_14`, `upper_wick_ratio`, `lower_wick_ratio`, `distance_from_20d_low`, `relative_strength_usd`, plus the original OHLCV columns. Update `__init__.py` to re-export `compute_all_indicators` and `compute_rsi`, `compute_ema`, `compute_sma`, `compute_atr`, `compute_adx`.
- **Test**: Integration test with 250-row synthetic OHLCV + EUR/USD data. Verify: all 16 indicator columns present, no NaNs after row 252 (warmup), correct dtypes (float64 for all except ema_fan which is bool).
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/`
- **Done when**: Assembly produces correct DataFrame, all columns present, mypy clean.
- [x] Completed

### Task 9: Rolling Z-Score Utility [1B.11]
- **Files**: `src/trading_advisor/indicators/composite.py`, `tests/test_composite.py`
- **Model**: sonnet
- **Action**: Implement `rolling_zscore(series, window=252)`. Formula: `(x - rolling_mean(x, window)) / rolling_std(x, window)`. Edge cases: insufficient history → NaN, zero std dev → NaN (not inf). Also define `Signal` enum in this file.
- **Test**: Known distribution (e.g., range 1-252) → last value z-score calculable. Zero std (constant series) → NaN. Series shorter than window → all NaN.
- **Verify**: `uv run pytest tests/test_composite.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/composite.py`
- **Done when**: Z-score matches hand-calculated values, edge cases return NaN, mypy clean.
- [x] Completed

### Task 10: Composite Components (all 5) [1B.12 + 1B.13 + 1B.14 + 1B.15 + 1B.16]
- **Files**: `src/trading_advisor/indicators/composite.py`, `tests/test_composite.py`
- **Model**: opus
- **Action**: Implement all 5 component functions. Each computes a raw value then z-scores it via `rolling_zscore`:
  1. `momentum_component`: `raw = close[t-21] / close[t-126] - 1`, z-score over 252d
  2. `trend_component`: `raw = (close > sma_50) + (close > sma_200) + (sma_50 > sma_200)` → int 0-3, z-score over 252d
  3. `rsi_filter_component`: `raw = 50 - abs(rsi_14 - 50)` → 0-50, z-score over 252d
  4. `atr_volatility_component`: `percentile = percentile_rank(atr, 252d)`, `raw = 1 - abs(percentile - 50) / 50` → 0.0-1.0, z-score over 252d
  5. `sr_proximity_component`: `raw = 1 - (high_20d - close) / close`, z-score over 252d
- **Test**: Each component: verify raw value range, verify z-score is applied. Momentum: trending up → positive raw. Trend: golden cross + above both MAs → raw = 3. RSI filter: RSI=50 → raw = 50 (max). ATR: median ATR → raw near 1.0. SR: close at 20d high → raw = 1.0.
- **Verify**: `uv run pytest tests/test_composite.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/composite.py`
- **Done when**: All 5 components produce correct raw and z-scored values, mypy clean.
- [x] Completed

### Task 11: Composite Assembly + Signal Classification [1B.17]
- **Files**: `src/trading_advisor/indicators/composite.py`, `src/trading_advisor/indicators/__init__.py`, `tests/test_composite.py`
- **Model**: sonnet
- **Action**: Implement `compute_composite(indicators_df)` — calls all 5 component functions on the DataFrame, computes weighted sum: `mom_z*0.44 + trend_z*0.22 + rsi_z*0.17 + atr_z*0.11 + sr_z*0.06`. Adds columns for each component's raw and z-scored values, the composite score, and the signal classification. Implement `classify_signal(composite_value)` → Signal enum using thresholds: >2.0 STRONG_BUY, >1.5 BUY, <-2.0 STRONG_SELL, <-1.5 SELL, else NEUTRAL. Update `__init__.py` to re-export `compute_composite`, `classify_signal`, `Signal`.
- **Test**: Pre-computed composite from known component z-scores. Threshold edge cases: exactly 1.5 → BUY, exactly 2.0 → STRONG_BUY, exactly -1.5 → SELL, exactly -2.0 → STRONG_SELL, 0.0 → NEUTRAL. Integration test: full pipeline from OHLCV → indicators → composite → signal.
- **Verify**: `uv run pytest tests/test_composite.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/composite.py`
- **Done when**: Composite matches weighted sum, signals classify correctly at all thresholds, mypy clean.
- [x] Completed

### Task 12: Pullback Threshold Validation [1B.18]
- **Files**: `src/trading_advisor/indicators/technical.py`, `tests/test_indicators.py`
- **Model**: sonnet
- **Action**: Add `compute_pullback_distance(close: pd.Series, ema_8: pd.Series) -> pd.Series` returning `(close - ema_8) / ema_8`. This is the metric used later by the Pullback Zone guard. The histogram plotting / analysis is a one-off script, not a library function — skip implementing the script, just add the distance calculation.
- **Test**: Close above EMA_8 → positive. Close below → negative. Close == EMA_8 → 0.0.
- **Verify**: `uv run pytest tests/test_indicators.py -v --no-cov && uv run mypy --strict src/trading_advisor/indicators/technical.py`
- **Done when**: Pullback distance calculated correctly, mypy clean.
- [x] Completed

### Task 13: TradingView Verification Script [1B.10]
- **Files**: `scripts/verify_indicators.py`
- **Model**: haiku
- **Action**: Create a CLI script that reads stored OHLCV data, computes all indicators via `compute_all_indicators`, and prints RSI_14, EMA_8, SMA_200, ADX_14, ATR_14 for 5 random dates in a side-by-side table format for manual comparison against TradingView. No automated tests needed — this is a manual verification tool.
- **Test**: N/A (manual verification script)
- **Verify**: `uv run mypy --strict scripts/verify_indicators.py`
- **Done when**: Script runs and prints formatted output, mypy clean.
- [x] Completed
