# Multi-Agent Campaign Blueprints

This document outlines the architectural campaigns for implementing a multi-agent, multi-provider CLI workflow. Each phase of the software development lifecycle is treated as a distinct "campaign" assigned to the AI model best suited for its architectural strengths. 

These blueprints follow the 13-element Planning Contract standard.

---

## Campaign 1: Discovery & Planning
**Assigned Model:** Gemini 1.5 Pro (via Gemini CLI)
**Primary Commands:** `/discover`, `/planner`

1. **Title:** Comprehensive Codebase Discovery and Strategic Planning
2. **Goal:** Ingest the entire target repository, understand its architectural patterns, and generate a precise, actionable implementation plan for a user's feature request.
3. **Exit Criteria:** A valid `planning-contract.md` is generated, correctly referencing existing cross-file dependencies without hallucinating missing components.
4. **Impact:** Sets the foundational truth for all subsequent agents. Errors here compound across the entire lifecycle.
5. **Roster:** Gemini CLI (Agent: Lead Architect)
6. **Graph:** User Input -> `/discover` (Context Building) -> `/planner` (Strategy Generation) -> `planning-contract.md`
7. **Ownership:** Gemini CLI handles all bulk file reading and initial architectural synthesis.
8. **Conflicts:** May conflict with existing outdated documentation; must prioritize reading actual source code over stale Markdown files.
9. **Integration:** Outputs standard markdown/JSON schema that the `/manager` command can seamlessly parse.
10. **Schema:** Standard 13-element Planning Contract Markdown format.
11. **Risk:** Token limits (mitigated by Gemini's massive 1M-2M context window).
12. **Verification:** The generated `planning-contract.md` is validated against a schema validator to ensure all 13 elements are present and actionable.
13. **Docs:** Updates `ARCHITECTURE.md` temporarily to reflect the proposed state.

---

## Campaign 2: Task Routing & Orchestration
**Assigned Model:** GPT-4o (via Codex/Aider)
**Primary Commands:** `/manager`, `/loop-master`

1. **Title:** High-Speed Task Delegation and State Management
2. **Goal:** Parse the `planning-contract.md`, break it into discrete, isolated coding tickets, and orchestrate the execution loop.
3. **Exit Criteria:** All sub-tasks from the planning contract are queued, dispatched to the Ship agent, and tracked to completion or failure.
4. **Impact:** Ensures the project doesn't stall. Maintains the operational cadence of the multi-agent system.
5. **Roster:** GPT-4o (Agent: Project Manager / Dispatcher)
6. **Graph:** `planning-contract.md` -> `/manager` -> Task Queue -> `/loop-master` -> Task Dispatch
7. **Ownership:** GPT-4o owns the state of the active execution loop but does not write application code.
8. **Conflicts:** Race conditions if multiple tasks modifying the same file are dispatched concurrently.
9. **Integration:** Reads Markdown from Gemini; passes strict JSON payloads containing file paths and instructions to Claude.
10. **Schema:** JSON Task Queue (Task ID, Target File, Instruction, Status).
11. **Risk:** Improperly scoping tasks (sending a task that is too large).
12. **Verification:** Manager validates that the number of completed tasks matches the number of tasks required by the planning contract.
13. **Docs:** Maintains a `.gemini/run-state.json` file logging task progression.

---

## Campaign 3: Execution & Implementation
**Assigned Model:** Claude 3.5 Sonnet (via Claude CLI)
**Primary Commands:** `/ship`

1. **Title:** Surgical Code Generation and Refactoring
2. **Goal:** Execute highly specific, tightly scoped coding tasks on individual files or small clusters of files based on explicit instructions from the Manager.
3. **Exit Criteria:** The target file is modified, idiomatic, syntactically valid, and fulfills the specific sub-task instruction.
4. **Impact:** The actual manifestation of the feature or bug fix. The quality of the final product relies entirely on this phase.
5. **Roster:** Claude 3.5 Sonnet (Agent: Senior Developer)
6. **Graph:** Task Dispatch -> `/ship` -> File Modification -> Commit/Save
7. **Ownership:** Claude owns the source code implementation for the duration of the specific sub-task.
8. **Conflicts:** May introduce logic that violates the broader architecture if the Manager provided insufficient context in the sub-task.
9. **Integration:** Receives input via CLI arguments/stdin from the Loop Master; outputs modified files directly to the file system.
10. **Schema:** Standard file outputs (TypeScript, Python, etc.) + Git diffs.
11. **Risk:** Hallucinating undefined variables or methods from files outside its limited context window.
12. **Verification:** Local language server protocol (LSP) checks or basic linters (`eslint`, `mypy`) run immediately post-edit.
13. **Docs:** Adds inline code comments and updates docstrings for the modified functions.

---

## Campaign 4: Quality Assurance & Review
**Assigned Model:** Gemini 1.5 Pro (via Gemini CLI)
**Primary Commands:** `/qa`

1. **Title:** Contextual Code Review and Integration Testing
2. **Goal:** Evaluate the completed work against the original `planning-contract.md` and the entire surrounding codebase to detect regressions or architectural drift.
3. **Exit Criteria:** The test suite passes, and the QA agent confirms the integration matches the original architectural intent.
4. **Impact:** Prevents isolated, functional code (written by Claude) from breaking the broader system. Ensures the original Goal is actually met.
5. **Roster:** Gemini CLI (Agent: Principal Reviewer / QA Engineer)
6. **Graph:** Modified Files -> `/qa` -> Run Test Suite -> (Pass: Finish | Fail: Send feedback to `/manager`)
7. **Ownership:** Gemini owns the final sign-off before the campaign loop is terminated.
8. **Conflicts:** May reject Claude's code due to overly strict stylistic differences rather than actual bugs.
9. **Integration:** Can optionally ingest multimodal inputs (e.g., screenshots of the UI after Claude's changes) to verify visual requirements.
10. **Schema:** Test runner output logs (stdout/stderr) and Markdown review feedback.
11. **Risk:** False positives in test failures due to flaky tests rather than bad code.
12. **Verification:** Confirms the empirical reproduction of the fix or feature by executing standard project test commands (e.g., `npm test`, `pytest`).
13. **Docs:** Appends an "Outcome and Verification" section to the original `planning-contract.md` closing out the campaign.
