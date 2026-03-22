# CLAUDE.md — WealthOps

## What This Project Is

WealthOps is a trading advisory system. It monitors daily candles, scores momentum, checks safety guards, and sends trade signals + daily briefings via Telegram. No auto-execution. The user reads the signal and manually places orders on IG.

## Python Environment

**ALWAYS use `uv run` to execute any Python tool.** Never use `.venv/bin/`, `python -m`, or bare commands.

## Verification Commands

Run these before every commit:

```bash
uv run mypy --strict src/
uv run pytest --cov --cov-branch --cov-fail-under=100
```

Ruff runs automatically via the Stop hook — do not run it manually.

- 100% line + branch coverage enforced. `pytest` fails under 100%.
- `# pragma: no cover` only with a comment explaining why.
- All functions must have type annotations. `from __future__ import annotations` at the top of every module.
- For coding style details, read `docs/coding-standards.md` before writing any code.

## Commits

- Atomic: one logical change per commit.
- Format: `type: short description` (feat, fix, refactor, test, docs)
- Stage files explicitly by name. Do not use `git add -A` or `git add .`.

## File Map

Project docs live in `docs/`. Only read what's relevant:

| If your task involves... | Read... |
|--------------------------|---------|
| Session start / what to work on next | `docs/progress.md` |
| Data pipeline, indicators, guards, signals, backtest | `docs/strategy/phase1-plan.md` (relevant task section only) |
| System design, directory structure, deployment | `docs/architecture.md` |
| Writing any code | `docs/coding-standards.md` |

Do NOT load all docs at once. Load only what the current task requires.

## Sub-Agent Rules

**One implementer sub-agent at a time, sequentially.** Build one module, verify it passes all checks, then move to the next.

When dispatching to the implementer, give file paths — not file contents. The implementer can read files itself.

Only use the `reviewer` sub-agent after all implementation is complete.

## Context Management

**Compact at logical breakpoints, not when the window is full.** Compact after finishing a module before starting the next, after a failed approach before trying a new one. Don't compact mid-implementation.
