# Quick

Small, well-understood changes. No sub-agents, no plan documents.

Use for: bug fixes, config changes, small refactors, adding a single function, dependency updates.

Do NOT use for: new features, architectural changes, anything touching more than 3 files. Use `/build` instead.

## Process

1. **State what you're doing** in one sentence. If it takes more than one sentence, use `/build`.
2. **Write the test first** (if applicable).
3. **Make the change.**
4. **Verify:** Run the verification commands from CLAUDE.md.
5. **Commit:**
   ```bash
   git add [specific files]
   git commit -m "type: short description"
   ```
6. **Update the relevant plan file** if the change completes a tracked task or fixes a tracked bug.

If mid-task you realize it's bigger than expected: STOP. Tell the user it needs `/build`.
