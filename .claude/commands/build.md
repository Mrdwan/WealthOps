# Build

You are the orchestrator running the full build pipeline. You own this from start to finish.

## Mode

If `$ARGUMENTS` contains "auto" or "autonomous": run in **auto mode**. Skip all checkpoints, make decisions autonomously, log them in the plan under a "Decisions" section. Create a feature branch (`feat/[short-name]`) before starting. Never ask questions — if something is ambiguous, decide and document.

Otherwise: run in **interactive mode** (default). Ask questions and wait for approval at checkpoints.

## Phase 1: Understand

Check `docs/plans/` for an existing spec matching this feature. If found, skip this phase — use the spec as input.

Otherwise, ask the user questions until you fully understand:
- What problem this solves
- Edge cases and error handling
- How it interacts with existing code
- What "done" looks like

Present your understanding back in short chunks. Get confirmation.

In auto mode: skip this phase entirely. Use the user's request as-is, or read the existing spec.

## Phase 2: Plan

Derive a feature slug from the feature name (e.g., "Data Pipeline" → `data-pipeline`).

Write `docs/plans/<feature-slug>.plan.md` containing:

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

**Interactive mode: STOP HERE.** Present the plan to the user. Wait for approval before proceeding.

**Auto mode:** Skip this checkpoint. Proceed immediately.
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
   - Check mypy output from the implementer
   - If the implementer didn't run checks, run them yourself (see CLAUDE.md for verification commands)
   - After 2 failed dispatches for the same task, stop and report the blocker. Do not loop.

4. **Commit**:
   ```bash
   git add [specific files]
   git commit -m "type: [task short name]"
   ```

5. **Mark complete** in the plan file, move to next task.

If you need to explore multiple parts of the codebase before planning, use parallel Explore agents (background) to investigate independently. Synthesize their findings before planning.

## Phase 4: Review

After all tasks are done:

1. Use the `reviewer` agent. Tell it exactly which files to review (list the files created/modified during execution).
2. If it finds CRITICAL or BUG issues, fix them, then re-review.
3. Run the full verification commands from CLAUDE.md.

## Phase 5: Report

1. Update `docs/PROGRESS.md`:
   - Add a row to the Recent Activity table with today's date and what was built
   - Check off completed items in the Task Checklist
   - Move any resolved open questions to Decisions Made

2. Tell the user:
   - What was built (files created/modified)
   - Decisions made during implementation
   - Test results and coverage
   - Any issues found and how they were resolved

Done.
