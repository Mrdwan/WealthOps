# CLAUDE.md — WealthOps

## What This Project Is

WealthOps is a trading advisory system. It monitors daily candles, scores momentum, checks safety guards, and sends trade signals + daily briefings via Telegram. No auto-execution. The user reads the signal and manually places orders on IG.

## Design Principles

- **SRP**: each module/class does one thing.
- **OCP**: new guards, providers, backends added via ABC — not modifying existing code.
- **LSP**: every implementation of an ABC must be a drop-in substitute — honour the contract, no surprises.
- **DIP**: depend on abstractions, not concretions. All dependencies injected via constructor. No module-level singletons or global state.
- **DRY**: single source of truth for every piece of knowledge. If you're copying logic, extract it.
- **Fail fast**: bad data or broken logic must raise immediately. No silent fallbacks that mask wrong signals.
- **Pure logic separate from I/O**: strategy code never does I/O directly. This is what lets backtest and live share the same path.

## Python Environment

**ALWAYS use `uv run` to execute any Python tool.** Never use `.venv/bin/`, `python -m`, or bare commands.

## Verification Commands

Run these before every commit:

```bash
uv run mypy --strict src/
uv run pytest --cov --cov-branch --cov-fail-under=100
```

Ruff runs automatically via the Stop hook — do not run it manually.

## Commits

- Atomic: one logical change per commit.
- Format: `type: short description` (feat, fix, refactor, test, docs)
- Stage files explicitly by name. Do not use `git add -A` or `git add .`.

## Branching

All work happens on feature branches. Never commit directly to main.
- `/build` auto mode creates the branch automatically.
- For `/quick`, `/debug`, or manual work: check your branch before starting. If on main, create a feature branch first: `git checkout -b type/short-name`
- This is enforced by a PreToolUse hook — commits to main will be blocked.

## File Map

Project docs live in `docs/`. Only read what's relevant:

| If your task involves... | Read... |
|--------------------------|---------|
| Session start / what to work on next | `docs/strategy/phase1-plan.md` (Task Checklist — find first uncompleted task) |
| Resuming a planned feature | `docs/plans/` (check for existing spec/plan) |
| Data pipeline, indicators, guards, signals, backtest | `docs/strategy/phase1-plan.md` (relevant task section only) |
| System design, directory structure, deployment | `docs/architecture.md` |

Do NOT load all docs at once. Load only what the current task requires.

## Sub-Agent Rules

**One implementer sub-agent at a time, sequentially.** Build one module, verify it passes all checks, then move to the next.

When dispatching to the implementer, give file paths — not file contents. The implementer can read files itself.

Use the `reviewer` sub-agent after each implementer task to check code quality and test meaningfulness via mutation testing.

After 2 failed attempts on the same task, stop, report the blocker, and ask the user. Do not loop.

For risky or experimental tasks, use `isolation: "worktree"` when dispatching to the implementer. This gives it an isolated copy of the repo. Review changes before merging.

### Context-Efficient Reading (Strict)

**Opus may read at most 2 files directly per phase** — only when the content drives an immediate decision (e.g., the plan file to find the next task, a spec to choose an approach).

**Everything else goes to an Explore agent.** Any time you need to understand existing code, check what's implemented, survey tests, or gather context across multiple files — dispatch an Explore agent with a focused question. Use the agent's summary, not raw file contents.

Never read files "just to see what's there." If you catch yourself about to read a third file, stop and delegate instead.

## Context Management

**Compact at logical breakpoints, not when the window is full.** Compact after finishing a module before starting the next, after a failed approach before trying a new one. Don't compact mid-implementation.

When compacting, preserve: modified file list, test results, type-check results, current task status in the active plan file, key decisions made. Discard exploration output, failed approaches, verbose tool output.
