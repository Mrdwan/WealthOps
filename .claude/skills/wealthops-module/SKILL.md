---
name: wealthops-module
description: >
  Use when creating or modifying a WealthOps Python module. Enforces project
  coding standards, test structure, type safety, and the implementation-then-review workflow.
---

# WealthOps Module Workflow

When creating or modifying a module:

## 1. Understand the task
- Read the relevant section of `phase1-plan.md` for the spec
- Read `Architecture.md` to understand where the module fits in the directory structure
- Check `PROGRESS.md` for any notes from previous sessions about this task

## 2. Plan before coding
- Identify the public interface: what functions/classes, what inputs, what outputs
- Identify dependencies that need to be injected
- Identify what needs to be mocked in tests
- If the module depends on another module that doesn't exist yet, write the ABC/interface first

## 3. Implement
- Use the `implementer` sub-agent for the actual coding
- Write the module and its tests together, not sequentially
- Follow CODING_STANDARDS.md strictly

## 4. Verify
- `ruff check --fix && ruff format`
- `mypy --strict src/trading_advisor/`
- `pytest --cov --cov-branch` — must be 100% on both metrics
- If any check fails, fix before proceeding

## 5. Review
- Use the `reviewer` sub-agent to review the code
- Address any CRITICAL or BUG findings before committing
- STYLE findings should be fixed. NITs are optional.

## 6. Update progress
- Check off completed items in `PROGRESS.md`
- Log any decisions made in the Decisions Made table
- Add notes for the next task if relevant
