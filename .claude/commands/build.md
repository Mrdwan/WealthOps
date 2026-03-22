# Build

You are the orchestrator running the full build pipeline. You own this from start to finish.

## Phase 1: Understand

Ask the user questions until you fully understand:
- What problem this solves
- Edge cases and error handling
- How it interacts with existing code
- What "done" looks like

Present your understanding back in short chunks. Get confirmation.

## Phase 2: Plan

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

Every task must be self-contained enough for the `implementer` agent to execute with zero project context beyond what you give it.

Review the plan yourself for completeness and consistency before presenting it.

## <CHECKPOINT>

**STOP HERE.** Present the plan to the user. Wait for approval before proceeding.

Do NOT start implementation until the user says go.
</CHECKPOINT>

## Phase 3: Execute

For each task in dependency order:

1. **Prepare a task prompt** for the `implementer` agent. Include:
   - The exact task description (copy it — don't reference the plan file)
   - File paths to read (NOT inline content — the implementer reads files itself)
   - Test and verify instructions

2. **Dispatch**: "Use the implementer agent to: [full task prompt]"

3. **Review the result**:
   - Check test output passes
   - Check ruff and mypy output from the implementer
   - If the implementer didn't run mypy or ruff, run them yourself: `uv run ruff check . && uv run mypy --strict src/`
   - If failed, fix yourself or re-dispatch. Do not skip.

4. **Commit**:
   ```bash
   git add [specific files]
   git commit -m "type: [task short name]"
   ```

5. **Mark complete** in docs/PLAN.md, move to next task.

## Phase 4: Review

After all tasks are done:

1. Use the `reviewer` agent: "Use the reviewer agent to review the implementation."
2. If it finds CRITICAL or BUG issues, fix them via the `implementer` agent, then re-review.
3. Run the full check:
   ```bash
   uv run mypy --strict src/
   uv run pytest --cov --cov-branch --cov-fail-under=100
   ```
   Ruff runs automatically via the Stop hook — do not run it manually.

## Phase 5: Report

1. Update `docs/progress.md`:
   - Add a row to the Recent Activity table with today's date and what was built
   - Check off completed items in the Task Checklist
   - Move any resolved open questions to Decisions Made

2. Tell the user:
   - What was built (files created/modified)
   - Decisions made during implementation
   - Test results and coverage
   - Any issues found and how they were resolved

Done.
