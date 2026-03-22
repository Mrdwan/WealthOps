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

4. **Write SPEC.md.** Once the design is agreed, write `docs/SPEC.md` containing:
   - **Goal**: one paragraph on what this achieves
   - **Requirements**: numbered list of what must be true when done
   - **Technical approach**: how it will be built (architecture, key decisions)
   - **Out of scope**: what this does NOT cover
   - **Open questions**: anything unresolved (should be empty before moving to /plan)

## <HARD-GATE>

**YOU ARE FORBIDDEN FROM:**
- Writing any implementation code
- Creating any project files (except docs/SPEC.md)
- Running scaffolding commands (npm init, django-admin, etc.)
- Suggesting "let me just quickly set that up"
- Invoking any implementation tools

This session is THINKING ONLY. The moment you touch code, you have failed. If the user asks you to "just start coding," remind them to run `/plan` first after the spec is approved.

**The ONLY file you create is docs/SPEC.md.**
</HARD-GATE>

## When done

Tell the user: "Spec saved to docs/SPEC.md. Review it, then run `/plan` when ready."
