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

## 2: Plan

Write `docs/PLAN.md` containing:

```markdown
# Plan: [Feature Name]

## Goal
[One paragraph]

## File Map
- `src/...` — responsibility
- `tests/...` — tests for above

## Tasks

### Task 1: [Short name]
- **Files**: [exact paths]
- **Action**: [explicit instructions — self-contained, no assumed context]
- **Test**: [what test to write first, what to assert]
- **Verify**: `uv run pytest tests/test_x.py -v --no-cov`
- **Done when**: [concrete criteria]
- [ ] Completed
```

### 3. Execute
For each task in dependency order:

1. Prepare task prompt for the `implementer` agent (full task description + file contents inline).
2. Dispatch: "Use the implementer agent to: [full task prompt]"
3. Review result — check tests, run `uv run ruff check .` and `uv run mypy src/`.
4. If failed, re-dispatch.
5. Commit:
   ```bash
   uv run ruff check --fix . && uv run ruff format .
   git add -A
   git commit -m "type: [task short name]"
   ```
6. Mark complete in docs/PLAN.md, next task.

### 4. Review
Use the `reviewer` agent. Fix CRITICAL and BUG issues. Re-review if needed.

Run full checks:
```bash
uv run pytest
uv run mypy --strict src/
uv run ruff check .
```

### 5. Finalize

Commit any remaining changes. Then report to the user:

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
- **Every ambiguity gets logged** in docs/PLAN.md under a "Decisions" section so the user sees what you chose during PR review.
- **Never commit to main.** Everything goes on the feature branch.
- **If something is fundamentally blocked** (missing dependency, can't determine requirements), stop and explain what's blocking. Don't guess on architecture.
