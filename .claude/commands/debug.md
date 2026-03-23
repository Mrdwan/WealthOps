# Debug

You are debugging an issue. Follow this systematic process. Do NOT jump to solutions.

## Phase 1: Reproduce

Before anything else, reproduce the bug reliably.

- Get the exact steps, input, or command that triggers the issue
- Run it yourself and observe the actual behavior
- Document: **expected** vs **actual** behavior
- If you cannot reproduce it, say so and ask the user for more context

**Do not proceed to Phase 2 until you can reproduce the issue on demand.**

## Phase 2: Isolate

Narrow down the root cause. Change ONE thing at a time.

- **Binary search the scope**: which file, which function, which line?
- **Check recent changes**: `git log --oneline -10` and `git diff HEAD~3` — did this work before?
- **Add diagnostic output**: temporary prints/logs at key points to trace execution flow
- **Test assumptions**: if you think "X should be Y at this point," verify it. Don't assume.

**Form a hypothesis**: "The bug is caused by [specific thing] because [evidence]."

**Do not proceed to Phase 3 until you have a hypothesis backed by evidence.**

## Phase 3: Fix

**If on main, create a feature branch before making any changes:** `git checkout -b fix/<short-name>`.

Apply the minimal fix that addresses the root cause.

- Fix the root cause, not the symptom
- Do not refactor unrelated code while debugging
- Write a test that would have caught this bug (fails without fix, passes with fix)
- If the fix is larger than expected, stop and tell the user — it may need its own /build cycle

## Phase 4: Verify

- Run the reproduction steps again — the bug should be gone
- Run the new test — it should pass
- Run the full verification commands from CLAUDE.md — nothing else should break
- Commit with message: `fix: [what was wrong and why]`
- Update the relevant plan file if the bug fix completes a tracked item

## Rules

- **ONE variable at a time.** Never change multiple things and test. You won't know which fixed it.
- **No shotgun debugging.** "Let me try changing a few things" is forbidden. Diagnose first.
- **Preserve evidence.** Don't delete error messages, logs, or diagnostic output until the fix is verified.
- **If stuck after 3 attempts:** step back, re-examine your assumptions, and consider that the bug might be somewhere you haven't looked yet.
