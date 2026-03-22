---
paths:
  - "src/**"
---

- `from __future__ import annotations` at the top of every module.
- All dependencies injected via constructor. No module-level singletons or global state.
- Depend on abstractions (ABCs), not concretions. Use `StorageBackend`, not `LocalStorage`.
- Use `@dataclass(frozen=True)` for value objects. Mutable dataclasses only when state genuinely needs to change.
- No code at module level — no side effects on import.
- Google-style docstrings on all public functions and classes.
- Module order: docstring, future annotations, stdlib, third-party, local, constants, type aliases, classes/functions.
