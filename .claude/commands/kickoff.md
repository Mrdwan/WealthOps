Read CLAUDE.md, then follow the Workflow section:

1. Read PROGRESS.md. Find the next unchecked task or the current in-progress task. Check Recent Activity for context from previous sessions.
2. Assess the scope. If the task is too big or touches multiple unrelated concerns, break it into smaller sub-tasks. Update PROGRESS.md with the breakdown and report the plan to me before starting.
3. Read only the project docs relevant to this specific task (use the File Map in CLAUDE.md).
4. Propose an implementation plan. Tell me: what files you'll create or modify, what interfaces you'll define, what order you'll build in, and how you'll test it. Wait for my approval.
5. After I approve, execute using sub-agents. Verify each sub-agent's output. If checks fail, spawn new sub-agents to fix issues. Iterate until everything passes.
6. Run the reviewer sub-agent on the completed code. If it finds CRITICAL or BUG issues, fix them and re-review.
7. Report back to me with a summary of what was built, decisions made, and test results. Wait for my review before committing.
8. After I approve, update PROGRESS.md.
