# Gemini Enhancement Campaign: Global Context Briefing

This document outlines a high-impact campaign specifically designed to leverage Gemini's massive 1.5M-2M+ token context window to enhance its role as the 'Lead Architect' and 'Knowledge Bridge' for a multi-agent CLI team.

This blueprint follows the 13-element Planning Contract standard.

---

## Campaign 9: Global Context Briefing & State Synchronization
**Assigned Model:** Gemini 1.5 Pro
**Primary Command:** `/brief <task-id>`

1. **Title:** Multi-Agent Knowledge Transfer and Context-Aware Execution Briefs
2. **Goal:** Use Gemini's 2M context window to ingest the *entire* repository, all documentation, and the full active planning contract to generate an ultra-high-signal "Brief" for a specific sub-task. This brief provides a smaller-context agent (like Claude 3.5 Sonnet) with the "Global Context" it lacks for surgical execution.
3. **Exit Criteria:** A functional `/brief` command and instruction set are generated. The output of `/brief` for any given sub-task successfully includes all necessary cross-file dependencies and interface definitions, fitting within a 20k token window.
4. **Impact:** Drastically reduces hallucinations in smaller-context agents by providing them with exactly the global context they lack. Eliminates the need for Claude to perform its own discovery on every task.
5. **Roster:** Gemini 1.5 Pro (Agent: Principal Architect / Knowledge Bridge)
6. **Graph:** `planning-contract.md` + Repository Context -> `/brief <task-id>` -> `docs/briefs/task-<id>.md` -> Claude CLI (`/ship`)
7. **Ownership:** Gemini owns the synthesis of "Global Context into Local Actionable Knowledge".
8. **Conflicts:** If the repository is >2M tokens, Gemini must handle chunking or prioritized context selection.
9. **Integration:** Plugs into the `/manager` command's loop, being triggered before every `/ship` call to refresh the context for the implementation agent.
10. **Schema:** Contextual Brief Markdown (Interface Specs, Related Files, Dependency Signatures, Logic Constraints).
11. **Risk:** Providing *too much* irrelevant context that distracts the implementation agent (Claude).
12. **Verification:** A test run verifies that a Claude session using a Gemini-generated brief can successfully implement a cross-file refactor without being given access to the full repository itself.
13. **Docs:** Automatically logs generated briefs in `.gemini/briefs/history/` for auditability of the agent's knowledge state.
