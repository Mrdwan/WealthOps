# Brainstorm

You are starting a brainstorming session. Your goal is to understand what the user wants to build and produce a clear spec document.

## Process

1. **Ask questions first.** Do not assume you understand the requirement. Ask about:
   - What problem this solves
   - Who/what consumes the output
   - Edge cases and error handling
   - How this interacts with existing code
   - What "done" looks like

2. **Present the design in chunks.** After gathering enough info, present your understanding back in short sections (3-5 sentences each). Get approval section by section. Do not dump a wall of text.

3. **Challenge assumptions.** If the user's approach has obvious flaws or there's a simpler way, say so. Propose alternatives. This is the cheapest time to change direction.

4. **Write the spec.** Once the design is agreed, derive a feature slug from the feature name (e.g., "Guard System" → `guard-system`). Write `docs/plans/<feature-slug>.spec.md` containing:
   - **Goal**: one paragraph on what this achieves
   - **Requirements**: numbered list of what must be true when done
   - **Technical approach**: how it will be built (architecture, key decisions)
   - **Out of scope**: what this does NOT cover
   - **Open questions**: anything unresolved (should be empty before moving to /build)

## Constraints

Do not write implementation code, create project files (except the spec), run scaffolding commands, or invoke implementation tools. The only file you create is `docs/plans/<feature-slug>.spec.md`.

If the user asks to start coding, remind them to run `/build` after the spec is approved.

## When done

Tell the user: "Spec saved to `docs/plans/<feature-slug>.spec.md`. Review it, then run `/build` when ready to plan and implement."
