---
paths:
  - "tests/**"
---

- Always mock external APIs (requests.get, fredapi.Fred, Telegram API). Never make real network calls.
- Mock the INPUT (raw API response), assert the OUTPUT (what the function produces). Tests must fail if logic is broken, even with perfect mocks.
- Unit tests in `tests/unit/`, integration tests in `tests/integration/`.
- Use `pytest-mock` (`mocker` fixture) for mocking.
