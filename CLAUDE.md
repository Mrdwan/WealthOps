# CLAUDE.md — WealthOps

Read this file first. Every conversation.

## What This Project Is

WealthOps is a trading advisory system. It monitors daily candles, scores momentum, checks safety guards, and sends trade signals + daily briefings via Telegram. No auto-execution. The user reads the signal and manually places orders on IG. Distributed as a PyPI package that runs on a laptop, Raspberry Pi, or AWS Lambda.

## File Map — What to Read When

Project docs live in docs/. Read what's relevant to the current task:
- docs/progress.md — always check this first for current task and session history
- docs/strategy/ — strategy specs, one file per phase
- docs/architecture.md — system design, directory structure, deployment
- docs/coding-standards.md — read before writing any code

## Workflow

1. **Find the current task.** Read `docs/progress.md` to find the next unchecked item or in-progress task. Check the "Recent Activity" section for context from previous sessions.
2. **Assess scope.** If the task involves multiple modules or unrelated concerns, break it into smaller sub-tasks. Update `docs/progress.md` with the breakdown, then report the plan to the user before starting.
3. **Read only what's needed.** Use the file map above to load the relevant docs for this specific task. Don't load everything.
4. **Plan first.** Propose an implementation plan. Cover: what files to create/modify, what interfaces to define, what to test, what order to build in. Wait for user approval before writing code.
5. **Execute with sub-agents.** Use the `implementer` sub-agent for each module. Spawn parallel agents for independent work, sequential for dependent work. After each sub-agent returns, verify its output: run `ruff check --fix`, `ruff format`, `mypy --strict`, `pytest --cov --cov-branch`. If verification fails, spawn a new sub-agent to fix the issues. Iterate until all checks pass.
6. **Review with a fresh context.** Use the `reviewer` sub-agent to review the completed code. If the reviewer finds CRITICAL or BUG issues, spawn the `implementer` again to fix them, then re-run the reviewer. Repeat until clean.
7. **Report to the user.** Present a summary: what was built, what decisions were made, what the test results look like. Stop and wait for human review before committing.
8. **Update docs.** After user approval, update `docs/progress.md`: check off finished items, log decisions in the Decisions Made table, add notes for the next task in Recent Activity.

## Sub-Agent Routing

When breaking tasks into sub-tasks, use these rules:

**Parallel** (all conditions met): independent sub-tasks, no shared state, different files.
Example: writing `tiingo.py` and `fred.py` can happen in parallel since they don't share code.

**Sequential** (any condition): output of one feeds the next, shared files, unclear scope.
Example: write the indicator module first, then the composite module that depends on it.

**Explore agent** for read-only research: understanding existing code, checking file structure, reading docs.

## Settled Decisions (Don't Re-litigate)

- **EUR/USD as inverted DXY proxy** — same Tiingo forex endpoint as gold, no extra data source
- **Guard toggle system** — `GUARDS_ENABLED` config dict, ablation study decides which guards stay
- **StorageBackend ABC** — `LocalStorage` (default) + `S3Storage` (optional via `pip install wealthops[aws]`)
- **All config via `WEALTHOPS_*` env vars** — python-dotenv for local, SSM/Lambda env for AWS
- **CLI entry points** — `wealthops ingest`, `briefing`, `bot`, `backtest`, `health`
- **Telegram bot** — polling (laptop/Pi) + webhook (Lambda), same code
- **No vectorbt** — Trap Order logic too custom, write backtest loop with pandas
- **Volume excluded for XAU/USD** — weights redistribute proportionally across remaining 5 composite components
- **Starting capital** — €15,000
- **Two equal deployment targets** — laptop/Pi and AWS Lambda

## Context Management

**Compact at logical breakpoints, not when the window is full.** Run `/compact` after finishing research before starting implementation, after completing a task before starting the next, and after a failed approach before trying a new one. Don't compact mid-implementation since you'll lose file paths, variable names, and partial state.

**Token settings for sub-agents:** Use Sonnet for sub-agents (cheaper, fast enough for focused tasks). Use Opus for the main session when doing complex architectural reasoning or debugging.

**Keep context lean:** Don't load all project files at once. The file map above exists for a reason. If a task only touches the data pipeline, don't load the Telegram bot specs.

## Key Constraints

- **No lookahead bias:** signals use prior day's close. Never use today's data to decide today's action.
- **Backtest before infrastructure:** Tasks 1A-1F validate the strategy before building Telegram bot (1G) or deployment (1H).
- **Guards must earn their place:** ablation study determines which guards stay. Don't assume any guard is valuable until data proves it.
- **Real money:** this bot trades real euros. Every untested code path is a potential loss.
