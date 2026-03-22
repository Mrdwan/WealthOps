# Auto

Fully autonomous build. No human checkpoints. Create a branch, build the feature, leave it ready for PR review.

## Setup

```bash
git checkout -b feat/[short-feature-name]
```

## Pipeline

Run the full pipeline without stopping for approval:

### 1. Understand the task
Read the user's request. If anything is ambiguous, make a reasonable decision and document it in the plan. Do NOT ask questions — this is autonomous.

### 2. Plan

Write `docs/PLAN.md` with a Goal, File Map, and Tasks (same format as `/build`). Add a **Decisions** section documenting any ambiguities you resolved autonomously.

### 3. Execute
For each task in dependency order:

1. Prepare task prompt for the `implementer` agent (full task description + file paths to read — NOT inline content).
2. Dispatch: "Use the implementer agent to: [full task prompt]"
3. Review result — check tests, ruff, and mypy output from the implementer.
4. If failed, re-dispatch.
5. Commit:
   ```bash
   git add [specific files]
   git commit -m "type: [task short name]"
   ```
6. Mark complete in docs/PLAN.md, next task.

### 4. Review
Use the `reviewer` agent. Fix CRITICAL and BUG issues. Re-review if needed.

Run full checks:
```bash
uv run mypy --strict src/
uv run pytest --cov --cov-branch --cov-fail-under=100
```
Ruff runs automatically via the Stop hook — do not run it manually.

### 5. Finalize

1. Update `docs/progress.md` (add activity row, check off tasks, resolve open questions).
2. Commit any remaining changes.
3. Report to the user:

```
Branch `feat/[name]` is ready for review.

Summary:
- [what was built]
- [decisions made autonomously]
- [test results]
- [N commits on branch]

To review: git diff main..feat/[name]
```

## Rules

- **No questions.** Make reasonable decisions and document them.
- **Every ambiguity gets logged** in docs/PLAN.md under a "Decisions" section.
- **Never commit to main.** Everything goes on the feature branch.
- **Stage files explicitly.** Never use `git add -A` or `git add .`.
- **If something is fundamentally blocked** (missing dependency, can't determine requirements), stop and explain what's blocking. Don't guess on architecture.
