---
paths:
  - "src/**"
---

- `from __future__ import annotations` at the top of every module.
- All functions fully typed (parameters + return). `mypy --strict` enforced. No `Any` without justification.
- `@dataclass(frozen=True)` for value objects. Mutable dataclasses only when state genuinely needs to change.
- Never pass raw dicts or tuples for structured data.
- No code at module level — no side effects on import.
- Module order: docstring, future annotations, stdlib, third-party, local, constants, type aliases, classes/functions.
- Naming: modules `snake_case`, classes `PascalCase`, functions `snake_case`, constants `UPPER_SNAKE`, private `_leading_underscore`.
- Google-style docstrings on all public functions, classes, and modules.
- Error handling: specific exceptions only, no bare `except:`.
