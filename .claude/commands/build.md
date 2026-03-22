# Build

You are the orchestrator running the full build pipeline. You own this from start to finish.

## Mode

If `$ARGUMENTS` contains "auto" or "autonomous": run in **auto mode**. Skip all checkpoints, make decisions autonomously, log them in the plan under a "Decisions" section. Create a feature branch (`feat/[short-name]`) before starting. Never ask questions — if something is ambiguous, decide and document.

Otherwise: run in **interactive mode** (default). Ask questions and wait for approval at checkpoints.

## Phase 1: Understand

**If no feature is specified in `$ARGUMENTS`:** Read `docs/strategy/phase1-plan.md` Task Checklist. Find the first uncompleted task in dependency order. Use that as the feature. Skip to Phase 2.

**If a feature is specified:** Check `docs/plans/` for an existing spec matching this feature. If found, skip the rest of this phase — use the spec as input.

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

1. Update `docs/strategy/phase1-plan.md`:
   - Check off completed items in the Task Checklist
   - Move any resolved open questions to Decisions

2. Tell the user:
   - What was built (files created/modified)
   - Decisions made during implementation
   - Test results and coverage
   - Any issues found and how they were resolved

## Phase 6: Manual Testing Guide

At the end of every build session, provide the user a **Manual Testing Guide** specific to what was built. This is not optional — always include it.

### Structure:

**1. Prerequisites** — what the user needs before they can test:
- Services to install (databases, CLI tools, runtimes, etc.)
- API keys/tokens to obtain: where to sign up, what the env var is called, and how to set it

**2. Step-by-step testing** — concrete CLI commands or short `uv run wealthops ...` invocations to verify the feature works end-to-end with real data/services (not automated tests — those already ran). Never give raw Python code to paste — always use the project's CLI entry points or one-liner `uv run python -c "..."` if no CLI exists yet.

**3. Expected output** — what the user should see if everything is working. Include example output or descriptions like "You should see 2500+ rows of XAU/USD daily data from 2015 to today."

Be specific to what was built in this session. Do not give generic advice.

Done.
