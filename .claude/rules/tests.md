---
paths:
  - "tests/**"
---

- 100% line + branch coverage enforced. `# pragma: no cover` only with a comment explaining why.
- Mock the INPUT (raw API response, file content). Assert the OUTPUT (what the function produces). Tests must fail if logic is broken, even with perfect mocks.
- Mock all external calls: `requests.get`, `fredapi.Fred`, Telegram API. No real network calls.
- Unit tests in `tests/unit/`, integration tests in `tests/integration/`.
- Use `pytest-mock` (`mocker` fixture) for mocking.
