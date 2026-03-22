# WealthOps — Coding Standards

> This bot trades real money. Every shortcut is a future bug. If it's not typed, not tested, and not clean — it doesn't get committed.
>
> For examples and rationale, see `coding-standards-full.md`.

## Testing

- **100% line + branch coverage.** `pytest --cov --cov-branch` enforced. No exceptions.
- `# pragma: no cover` only with a comment explaining why.
- Mock the **input** (raw API response, file content). Assert the **output** (what the function produces). Tests must fail if logic is broken, even with perfect mocks.
- Mock all external calls: `requests.get`, `fredapi.Fred`, Telegram API. No real network calls in tests.
- Unit tests in `tests/unit/`, integration tests in `tests/integration/`.
- Use `pytest-mock` (`mocker` fixture) for mocking.

## Type Safety

- `mypy --strict` enforced. Every function has full type annotations (parameters + return).
- No `Any` unless absolutely necessary (and documented why).

## Data Structures

- `@dataclass(frozen=True)` for immutable value objects (e.g., `GuardResult`, `Signal`).
- Mutable `@dataclass` only when state genuinely needs to change.
- Never pass raw dicts or tuples for structured data.

## Design Principles

- **SRP**: each module/class does one thing.
- **Open/Closed**: new guards, providers, backends added via ABC — not modifying existing code.
- **DIP**: depend on abstractions, not concretions. Inject via constructor.
- All dependencies injected via constructor. No module-level singletons or global state.

## Code Style

- **Naming**: modules `snake_case`, classes `PascalCase`, functions `snake_case`, constants `UPPER_SNAKE`, private `_leading_underscore`.
- **Docstrings**: Google style on all public functions, classes, and modules.
- **Module order**: docstring, `from __future__ import annotations`, stdlib, third-party, local, constants, type aliases, classes/functions.
- **Error handling**: specific exceptions only, no bare `except:`, fail fast and loud.
- No code at module level — no side effects on import.

## Tooling

| Step | Tool |
|------|------|
| Lint + imports | `ruff check --fix` (runs automatically via Stop hook) |
| Format | `ruff format` (runs automatically via Stop hook) |
| Types | `mypy --strict` |
| Tests | `pytest --cov --cov-branch --cov-fail-under=100` |
