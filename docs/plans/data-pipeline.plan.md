# Plan: Data Pipeline (Task 1A)

## Goal

Fetch XAU/USD and EUR/USD daily OHLCV from Tiingo, macro data (VIX, T10Y2Y, FEDFUNDS) from FRED, validate all data, and store as parquet files via a StorageBackend abstraction. Support both bootstrap (historical backfill) and incremental daily updates.

## File Map

- `src/trading_advisor/storage/__init__.py` — package init, re-exports
- `src/trading_advisor/storage/base.py` — StorageBackend ABC
- `src/trading_advisor/storage/local.py` — LocalStorage (pathlib + pyarrow)
- `src/trading_advisor/config.py` — Settings dataclass, env var loading, storage factory
- `src/trading_advisor/data/base.py` — OHLCVProvider + MacroProvider ABCs
- `src/trading_advisor/data/validation.py` — OHLCV validation rules
- `src/trading_advisor/data/tiingo.py` — TiingoProvider (XAU/USD, EUR/USD)
- `src/trading_advisor/data/fred.py` — FredProvider (VIX, T10Y2Y, FEDFUNDS)
- `src/trading_advisor/data/ingest.py` — Ingest orchestrator (fetch → validate → store)
- `tests/test_storage.py` — StorageBackend + LocalStorage tests
- `tests/test_config.py` — Config loading tests
- `tests/test_validation.py` — OHLCV validation tests
- `tests/test_tiingo.py` — TiingoProvider tests (mocked HTTP)
- `tests/test_fred.py` — FredProvider tests (mocked fredapi)
- `tests/test_ingest.py` — Ingest orchestrator tests

## Tasks

### Task 1: StorageBackend ABC + LocalStorage
- **Files**: `src/trading_advisor/storage/__init__.py`, `src/trading_advisor/storage/base.py`, `src/trading_advisor/storage/local.py`
- **Action**:
  - Create `StorageBackend` ABC with four abstract methods: `read_parquet(key: str) -> pd.DataFrame`, `write_parquet(key: str, df: pd.DataFrame) -> None`, `read_json(key: str) -> dict[str, Any]`, `write_json(key: str, data: dict[str, Any]) -> None`. Add `exists(key: str) -> bool` for checking if a key exists before reading.
  - Create `LocalStorage(StorageBackend)` that maps keys to file paths under a configurable `data_dir` (pathlib.Path). Auto-create parent directories on write. Use `pyarrow.parquet` for parquet I/O. Use `json` stdlib for JSON I/O.
  - `read_parquet` raises `FileNotFoundError` if key doesn't exist. `read_json` raises `FileNotFoundError` if key doesn't exist.
  - `__init__.py` re-exports `StorageBackend` and `LocalStorage`.
- **Test**: Write tests first in `tests/test_storage.py`. Use `tmp_path` fixture. Test: write then read parquet roundtrip preserves data. Write then read JSON roundtrip. `exists` returns True/False correctly. `read_parquet` on missing key raises `FileNotFoundError`. `read_json` on missing key raises `FileNotFoundError`. Nested key paths (e.g. `ohlcv/XAUUSD_daily`) create subdirectories.
- **Verify**: `uv run pytest tests/test_storage.py -v --no-cov`
- **Done when**: All tests pass, mypy clean on storage module.
- [x] Completed

### Task 2: Config module
- **Files**: `src/trading_advisor/config.py`, `tests/test_config.py`
- **Action**:
  - Define a `Settings` frozen dataclass with fields: `tiingo_api_key: str`, `fred_api_key: str`, `telegram_bot_token: str`, `telegram_chat_id: str`, `telegram_heartbeat_chat_id: str` (default `""`), `storage_type: str` (default `"local"`), `data_dir: Path` (default `Path("./data")`), `s3_bucket: str` (default `""`), `telegram_mode: str` (default `"polling"`), `log_level: str` (default `"INFO"`).
  - `load_settings() -> Settings`: reads env vars with `WEALTHOPS_` prefix (e.g. `WEALTHOPS_TIINGO_API_KEY`). Calls `dotenv.load_dotenv()` first. Raises `ValueError` with a clear message listing ALL missing required vars (don't fail on the first one).
  - `create_storage(settings: Settings) -> StorageBackend`: returns `LocalStorage(settings.data_dir)` when `storage_type == "local"`. Raises `ValueError` for unknown storage types (S3 comes in Task 1H).
- **Test**: Write tests first in `tests/test_config.py`. Use `monkeypatch` to set/unset env vars. Test: all vars set → Settings created correctly. Missing required var → ValueError with var name. Default values applied when optional vars absent. `create_storage` returns `LocalStorage` for `"local"`. `create_storage` raises for unknown type.
- **Verify**: `uv run pytest tests/test_config.py -v --no-cov`
- **Done when**: All tests pass, mypy clean on config module.
- [x] Completed

### Task 3: OHLCV Validation
- **Files**: `src/trading_advisor/data/validation.py`, `tests/test_validation.py`
- **Action**:
  - Define `@dataclass(frozen=True) class ValidationResult` with `valid: bool`, `errors: list[str]`, `warnings: list[str]`.
  - `validate_ohlcv(df: pd.DataFrame) -> ValidationResult`: checks all rules from the spec:
    1. Required columns present: open, high, low, close (volume optional)
    2. No null values in OHLC columns
    3. `high >= low` for every row
    4. `high >= open` and `high >= close` for every row
    5. `low <= open` and `low <= close` for every row
    6. Index is DatetimeIndex, monotonically increasing
    7. No duplicate timestamps
    8. Price within 5% of previous close → add to warnings (anomalies), not errors
  - Errors are hard failures (data is unusable). Warnings are anomalies to log but data is still usable.
  - Raise `ValueError` if DataFrame is empty.
- **Test**: Write tests first in `tests/test_validation.py`. Test: valid data passes. high < low → error. null values → error. duplicate timestamps → error. non-monotonic index → error. 6% price jump → warning but still valid. Empty DataFrame → ValueError. Missing column → error.
- **Verify**: `uv run pytest tests/test_validation.py -v --no-cov`
- **Done when**: All tests pass, mypy clean on validation module.
- [x] Completed

### Task 4: TiingoProvider
- **Files**: `src/trading_advisor/data/base.py`, `src/trading_advisor/data/tiingo.py`, `tests/test_tiingo.py`
- **Action**:
  - Update `data/base.py`: rename `DataProvider` to `OHLCVProvider`. Keep `fetch_ohlcv(symbol, start, end) -> pd.DataFrame` as the abstract method. The returned DataFrame must have a DatetimeIndex named `date` and columns: `open`, `high`, `low`, `close`. `volume` column optional (0.0 for forex).
  - Implement `TiingoProvider(OHLCVProvider)`:
    - Constructor takes `api_key: str` and `session: requests.Session | None = None` (for DI/testing).
    - Tiingo forex endpoint: `GET https://api.tiingo.com/tiingo/fx/{ticker}/prices` with params `startDate`, `endDate`, `resampleFreq=1day`, headers `Authorization: Token {api_key}`.
    - Tiingo forex tickers: `xauusd` for gold, `eurusd` for EUR/USD.
    - Response is JSON array of objects with fields: `date`, `open`, `high`, `low`, `close`. Parse into DataFrame.
    - Normalize column names to lowercase. Parse date strings to DatetimeIndex. Sort by date.
    - Raise `RuntimeError` on non-200 response with status code and body snippet.
- **Test**: Write tests first in `tests/test_tiingo.py`. Mock `requests.Session.get` to return canned JSON responses. Test: successful fetch returns correct DataFrame shape and dtypes. Correct URL and headers constructed. Non-200 response raises RuntimeError. Empty response returns empty DataFrame. Date parsing handles Tiingo's ISO format.
- **Verify**: `uv run pytest tests/test_tiingo.py -v --no-cov`
- **Done when**: All tests pass, mypy clean.
- [x] Completed

### Task 5: FredProvider
- **Files**: `src/trading_advisor/data/base.py`, `src/trading_advisor/data/fred.py`, `tests/test_fred.py`
- **Action**:
  - Add `MacroProvider` ABC to `data/base.py` with abstract method `fetch_series(series_id: str, start: str, end: str) -> pd.DataFrame`. Returns DataFrame with DatetimeIndex named `date` and a single `value` column.
  - Implement `FredProvider(MacroProvider)`:
    - Constructor takes `api_key: str` and `fred_client: Fred | None = None` (for DI/testing). If `fred_client` is None, create `Fred(api_key=api_key)`.
    - `fetch_series` calls `self._fred.get_series(series_id, observation_start=start, observation_end=end)`.
    - `fredapi.Fred.get_series` returns a `pd.Series` with DatetimeIndex. Convert to DataFrame with `value` column. Drop NaN rows.
    - Supported series: `VIXCLS` (VIX), `T10Y2Y` (yield curve), `FEDFUNDS` (fed funds rate).
    - Raise `RuntimeError` if the fredapi call fails.
- **Test**: Write tests first in `tests/test_fred.py`. Mock `fredapi.Fred.get_series` to return canned Series. Test: successful fetch returns DataFrame with correct shape. NaN rows dropped. fredapi error raises RuntimeError. Empty series returns empty DataFrame.
- **Verify**: `uv run pytest tests/test_fred.py -v --no-cov`
- **Done when**: All tests pass, mypy clean.
- [x] Completed

### Task 6: Data Ingest Pipeline
- **Files**: `src/trading_advisor/data/ingest.py`, `src/trading_advisor/data/__init__.py`, `tests/test_ingest.py`
- **Action**:
  - Create `DataIngestor` class:
    - Constructor takes `ohlcv_provider: OHLCVProvider`, `macro_provider: MacroProvider`, `storage: StorageBackend`, `validator: Callable` (default `validate_ohlcv`).
    - `ingest_ohlcv(symbol: str, start: str, end: str, storage_key: str) -> ValidationResult`:
      1. Fetch data from provider.
      2. If storage key exists, read existing data, find the last date, fetch only new data from `last_date + 1 day`.
      3. Validate the new data.
      4. If valid: concatenate with existing data (dedup on index), write to storage. Return result.
      5. If invalid: raise `ValueError` with validation errors. Do NOT write invalid data.
    - `ingest_macro(series_id: str, start: str, end: str, storage_key: str) -> None`:
      1. Fetch series from macro provider.
      2. If storage key exists, read existing, fetch only new data from last date + 1 day.
      3. Concatenate, dedup, write to storage. (No OHLCV validation for macro data.)
    - `run_daily_ingest(end_date: str) -> dict[str, ValidationResult]`:
      1. Ingest XAU/USD OHLCV → key `ohlcv/XAUUSD_daily`
      2. Ingest EUR/USD OHLCV → key `ohlcv/EURUSD_daily`
      3. Ingest VIX → key `macro/VIXCLS`
      4. Ingest T10Y2Y → key `macro/T10Y2Y`
      5. Ingest FEDFUNDS → key `macro/FEDFUNDS`
      6. Return dict of symbol → ValidationResult for OHLCV assets.
      7. Use a default start date of `"2015-01-01"` for bootstrap (10 years of data).
  - Update `data/__init__.py` to re-export key classes.
- **Test**: Write tests first in `tests/test_ingest.py`. Use mock providers and an in-memory or tmp_path storage. Test: fresh ingest writes data. Incremental ingest only fetches new dates and appends. Invalid data raises ValueError and doesn't write. `run_daily_ingest` calls all providers. Dedup works when overlapping dates exist.
- **Verify**: `uv run pytest tests/test_ingest.py -v --no-cov`
- **Done when**: All tests pass, mypy clean. Full `uv run mypy --strict src/` and `uv run pytest --cov --cov-branch --cov-fail-under=100` pass.
- [x] Completed

## Decisions

- **pytest-mock added as dev dependency** — needed for mocking `requests.Session` in TiingoProvider tests and consistent with `.claude/rules/tests.md`.
- **Combined validation in ingest** — after review, added validation of the concatenated (existing + new) DataFrame to catch corruption introduced during merge.
- **Path traversal guard in LocalStorage** — added `is_relative_to` check to prevent keys from escaping the data directory.
- **FRED incremental fetch limitation** — FRED series that backfill/revise prior dates may have stale values since we fetch from `last_date + 1 day`. Documented as a known limitation; acceptable for daily-frequency macro data.
