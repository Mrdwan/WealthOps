# CLAUDE.md — WealthOps

## What This Project Is

WealthOps is a trading advisory system. It monitors daily candles, scores momentum, checks safety guards, and sends trade signals + daily briefings via Telegram. No auto-execution. The user reads the signal and manually places orders on IG.

## Python Environment

**ALWAYS use `uv run` to execute any Python tool.** Never use `.venv/bin/`, `python -m`, or bare commands.

## Development Rules

### TDD
- Write a failing test FIRST, then the minimal code to pass it.
- Code written before a test: delete it, write the test, watch it fail, rewrite.

### Coverage
- 100% line + branch coverage enforced. `pytest` fails under 100%.
- Use `# pragma: no cover` only with a comment explaining why.

### Types
- All functions must have type annotations. `from __future__ import annotations` at the top of every module.

### Formatting
- Before every commit: `uv run ruff check --fix . && uv run ruff format .`
- Ruff handles linting, formatting, and import sorting. No Black, no Flake8, no isort.

### Debugging
When something fails, follow this sequence — do not skip steps:
1. **Reproduce** — get the exact failure, run it yourself
2. **Isolate** — change ONE thing at a time, check `git log` for recent changes
3. **Fix** — minimal fix for the root cause, not the symptom
4. **Verify** — run the fix, run the test suite, confirm nothing else broke

### Commits
- Atomic: one logical change per commit.
- Format: `type: short description` (feat, fix, refactor, test, docs)

## File Map

Project docs live in `docs/`. Read what's relevant to the current task:
- `docs/progress.md` — always check this first for current task and session history
- `docs/strategy/` — strategy specs, one file per phase
- `docs/architecture.md` — system design, directory structure, deployment
- `docs/coding-standards.md` — read before writing any code

## Sub-Agent Rules

**One implementer sub-agent at a time, sequentially.** Do not spawn parallel agents. Build one module, verify it passes all checks, then move to the next.

Only use the `reviewer` sub-agent after all implementation is complete.

## Context Management

**Compact at logical breakpoints, not when the window is full.** Compact after finishing a module before starting the next, after a failed approach before trying a new one. Don't compact mid-implementation.

**Keep context lean.** Don't load all project files at once. If a task only touches the data pipeline, don't load the Telegram bot specs.
