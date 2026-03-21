# WealthOps — Coding Standards

This document defines the mandatory coding standards for the WealthOps project. Every contributor (human or AI) must follow these rules. Violations must be caught by pre-commit hooks or CI before code is merged.

---

## Core Principles

### 1. 100% Test Coverage — Non-Negotiable

This bot handles **real money**. Bugs cost euros, not just time.

- Every module must have **100% line coverage** and **100% branch coverage**.
- `pytest --cov --cov-branch` is enforced via pre-commit. **Commits are rejected if either metric drops below 100%.**
- Branch coverage catches untested `if/else` paths that line coverage misses. Both are required.
- The only exceptions are in `[tool.coverage.run] omit` (e.g. `runner.py`, CLI entry points).
- If you add code, you add tests. No exceptions.

### 2. Tests Must Be Meaningful

Tests must validate **actual behavior**, not just confirm that mocks return what you told them to return.

**❌ BAD — Tests nothing, always passes even if function is broken:**
```python
def test_fetch_ohlcv(mocker):
    fake_data = pd.DataFrame({"open": [1.0], "close": [2.0]})
    mocker.patch("trading_advisor.data.tiingo.requests.get", return_value=fake_data)
    result = provider.fetch_ohlcv("XAUUSD", "2024-01-01", "2024-01-02")
    # This just checks that the mock returned what we told it to — useless
    assert result.equals(fake_data)
```

**✅ GOOD — Tests that the function actually transforms/validates/processes correctly:**
```python
def test_fetch_ohlcv_parses_api_response(mocker):
    # Mock returns RAW API response format (not the expected output)
    raw_api_response = [
        {"date": "2024-01-01T00:00:00+00:00", "open": 2060.5, "high": 2075.3,
         "low": 2055.1, "close": 2070.8, "volume": 0}
    ]
    mocker.patch("requests.get", return_value=MockResponse(json_data=raw_api_response))
    result = provider.fetch_ohlcv("XAUUSD", "2024-01-01", "2024-01-02")

    # Tests that the function ACTUALLY parses, renames, validates, and structures data
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert result.index.name == "date"
    assert result.iloc[0]["close"] == 2070.8
    assert len(result) == 1
```

**The rule:** Mock the **input** (raw API response, file content, external dependency). Assert the **output** (what the function actually produces from that input). The test should **fail if the function's logic is broken**, even though the mocks are perfect.

### 3. All External Calls Must Be Mocked

- No real API calls in tests. Ever.
- Mock at the boundary: `requests.get`, `fredapi.Fred`, file I/O, Telegram API.
- Use `pytest-mock` (`mocker` fixture) or `unittest.mock.patch`.
- Integration tests mock at a higher level (e.g., mock the `DataProvider` interface, not `requests.get`), but still no real network calls.

### 4. Two Test Layers

| Layer | What It Tests | Mocking Level |
|-------|--------------|---------------|
| **Unit tests** | Individual functions/methods in isolation | Mock all dependencies at the boundary |
| **Integration tests** | Multi-component flows (e.g., ingest → validate → store) | Mock external services (APIs, file I/O), real internal logic |

Both layers are required for every feature. Unit tests go in `tests/unit/`, integration tests in `tests/integration/`.

---

## Type Safety

### 5. Strict Type Checking (mypy --strict)

- Every function must have full type annotations (parameters and return type).
- No `Any` types unless absolutely necessary (and documented why).
- `mypy --strict` is enforced via pre-commit. Commits are rejected on type errors.
- **Why strict works here:** This is a brand new project — no legacy code to fight. `ignore_missing_imports` (already configured) handles third-party libs without `# type: ignore` noise.

### 6. Use Dataclasses for All Domain Objects

Never pass raw dicts or tuples for structured data. Define a dataclass (or `NamedTuple` for immutable data).

**❌ BAD:**
```python
def run_guard(data: dict) -> dict:
    return {"passed": True, "guard": "macro", "reason": "EUR/USD above 200 SMA"}
```

**✅ GOOD:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class GuardResult:
    passed: bool
    guard_name: str
    reason: str

def run_guard(data: MarketData) -> GuardResult:
    return GuardResult(passed=True, guard_name="macro", reason="EUR/USD above 200 SMA")
```

Use `frozen=True` for immutable value objects. Use `@dataclass` (mutable) only when state genuinely needs to change.

---

## Design Principles

> **Why not all 5 SOLID principles?** LSP and ISP are rooted in Java/C# class hierarchies. Python's duck typing makes them implicit — if a subclass breaks the contract, mypy catches it. We enforce the 3 that actively improve Python code quality.

### 7. SRP, Open/Closed, DIP

| Principle | What It Means Here |
|-----------|-------------------|
| **SRP** | Each module/class does one thing. `tiingo.py` fetches from Tiingo. `validator.py` validates data. They don't do both. |
| **Open/Closed** | New guards, data providers, or storage backends are added by implementing an ABC — not by modifying existing code. |
| **DIP** | Depend on abstractions, not concretions. Modules receive `StorageBackend`, not `LocalStorage`. |

### 8. Dependency Injection

All dependencies are injected via constructor or function parameters. No module-level singletons, no global state, no `import LocalStorage` deep inside business logic.

**❌ BAD:**
```python
class TiingoProvider:
    def __init__(self):
        self.storage = LocalStorage()  # Hard-coded dependency
```

**✅ GOOD:**
```python
class TiingoProvider:
    def __init__(self, http_client: HttpClient, storage: StorageBackend) -> None:
        self._http_client = http_client
        self._storage = storage
```

This makes testing trivial (inject mocks) and future changes painless (swap S3 for local).

### 9. DRY — Don't Repeat Yourself

- Extract shared logic into helper functions or base classes.
- Constants live in `config.py`, not scattered across modules.
- If you copy-paste code, you're doing it wrong.

---

## Code Style

### 10. Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Modules | `snake_case` | `macro_gate.py` |
| Classes | `PascalCase` | `TiingoProvider` |
| Functions/methods | `snake_case` | `fetch_ohlcv` |
| Constants | `UPPER_SNAKE` | `DEFAULT_LOOKBACK_DAYS` |
| Private | `_leading_underscore` | `_parse_response` |
| Type aliases | `PascalCase` | `OhlcvFrame` |

### 11. Docstrings

Every public function, class, and module must have a docstring. Use Google style:

```python
def validate_ohlcv(df: pd.DataFrame) -> ValidationResult:
    """Validate OHLCV data for consistency and completeness.

    Checks:
        - high >= low for all rows
        - No null values in OHLCV columns
        - Timestamps are monotonically increasing
        - No duplicate timestamps

    Args:
        df: DataFrame with OHLCV columns and a DatetimeIndex.

    Returns:
        ValidationResult with pass/fail status and list of anomalies.

    Raises:
        ValueError: If required columns are missing.
    """
```

### 12. Module Structure

Every Python module follows this order:
1. Module docstring
2. `from __future__ import annotations`
3. Standard library imports
4. Third-party imports
5. Local imports
6. Constants
7. Type aliases
8. Classes/functions
9. No code at module level (no side effects on import)

### 13. Error Handling

- Use specific exception types, never bare `except:`.
- Define custom exceptions in a `exceptions.py` module when needed.
- Functions should fail fast and loud — don't silently swallow errors.
- Log errors with context before re-raising.

---

## Tooling Enforcement

### Pre-commit Pipeline (must all pass to commit)

| Step | Tool | What It Catches |
|------|------|----------------|
| 1 | `ruff check --fix` | Lint errors, import sorting, dead code |
| 2 | `ruff format` | Code formatting |
| 3 | `mypy --strict` | Type errors |
| 4 | `pytest --cov --cov-branch` | Test failures, line or branch coverage below 100% |

### CI Pipeline (GitHub Actions)

Same as pre-commit, plus:
- Runs on every PR
- Matrix testing on Python 3.12+
- Coverage report uploaded as artifact

---

## Summary

> **If it's not typed, not tested, and not clean — it doesn't get committed.**
>
> This bot trades real money. Every shortcut is a future bug. Every untested path is a potential loss. Write code like your portfolio depends on it — because it does.
