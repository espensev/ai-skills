# Gemini Super-Skill Campaigns

This document outlines specialized campaigns designed exclusively for Gemini 1.5 Pro to leverage its unique architectural advantages: a massive 1M-2M+ token context window and native multimodal capabilities. These campaigns handle tasks that exceed the context limitations or modalities of other agents.

These blueprints follow the 13-element Planning Contract standard.

---

## Campaign 5: Repo-Scale Refactoring
**Assigned Model:** Gemini 1.5 Pro
**Primary Command:** `/epic-refactor`

1. **Title:** System-Wide Architectural Migration and Refactoring
2. **Goal:** Execute massive, cross-cutting migrations (e.g., framework upgrades, sweeping API layer rewrites, language ports) across hundreds of files simultaneously while maintaining strict topological dependency order.
3. **Exit Criteria:** All target files are migrated to the new architecture, the codebase compiles without errors, and the entire test suite passes.
4. **Impact:** Enables radical modernization of legacy systems that would otherwise require weeks of manual developer effort or cause other AI models to hallucinate mid-refactor.
5. **Roster:** Gemini CLI (Agent: Enterprise Architect)
6. **Graph:** Migration Request -> Context Ingestion (Full Repo) -> Dependency Graph Mapping -> Execution Loop (Batched Rewrites) -> Validation
7. **Ownership:** Gemini owns the entire migration state, ensuring that a change in File A is correctly mirrored in its downstream dependencies in File Z.
8. **Conflicts:** High risk of merge conflicts if other developers are pushing code to the same repository during the long-running migration.
9. **Integration:** Plugs into the `/qa` campaign for final verification of the migrated system.
10. **Schema:** Abstract Syntax Tree (AST) mapping and batch Git commits.
11. **Risk:** Unintended side effects in undocumented or dynamically typed parts of the codebase.
12. **Verification:** Comprehensive execution of integration and end-to-end tests; strict compiler/type-checker validation.
13. **Docs:** Automatically generates a `MIGRATION_CHANGELOG.md` detailing all architectural shifts made during the campaign.

---

## Campaign 6: Mega-Log Forensic Analysis
**Assigned Model:** Gemini 1.5 Pro
**Primary Command:** `/forensic-debugger`

1. **Title:** Multi-Gigabyte Production Log Ingestion and Root Cause Analysis
2. **Goal:** Ingest massive, raw production server logs, memory dumps, or network PCAP files, cross-reference them with the application source code, and pinpoint the exact line of code causing a cascade failure.
3. **Exit Criteria:** A definitive root-cause analysis report is generated, linking specific log anomalies to exact lines in the source code, accompanied by a proposed patch.
4. **Impact:** Drastically reduces Mean Time To Resolution (MTTR) for complex production outages without requiring developers to write custom grep scripts or ELK queries.
5. **Roster:** Gemini CLI (Agent: Site Reliability Engineer / SRE)
6. **Graph:** Raw Log Upload -> Log Synthesis & Anomaly Detection -> Source Code Cross-Referencing -> Patch Proposal
7. **Ownership:** Gemini owns the diagnostic process, tracing failures from the infrastructure layer down to the application logic.
8. **Conflicts:** Extracted logs may contain PII or sensitive data; strict data masking rules must be enforced before ingestion.
9. **Integration:** Feeds the resulting patch proposal directly to the `/manager` to be dispatched to Claude for implementation via `/ship`.
10. **Schema:** Standard Incident Report Markdown + Diff Patch.
11. **Risk:** False positives if logs are noisy or if the failure was caused by external state (e.g., third-party API outage) not visible in the code.
12. **Verification:** The proposed patch must be empirically verified by reproducing the exact failure state in a local/staging environment and confirming the fix resolves it.
13. **Docs:** Updates `postmortems/YYYY-MM-DD-incident.md` with the full forensic timeline.

---

## Campaign 7: Visual-to-Component UI Debugging
**Assigned Model:** Gemini 1.5 Pro
**Primary Command:** `/ui-test-engineer`

1. **Title:** Multimodal Visual Regression Resolution
2. **Goal:** Ingest video recordings, screenshots, or Cypress/Playwright failure artifacts of a UI bug, map the visual anomalies directly to the underlying frontend components (React/Vue/etc.), and fix the styling or rendering logic.
3. **Exit Criteria:** The visual bug is resolved, the updated component matches the desired design specification, and the visual test suite passes.
4. **Impact:** Bridges the gap between visual design and code. Solves layout shifts, responsive design failures, and rendering glitches that pure text-based models cannot perceive.
5. **Roster:** Gemini CLI (Agent: Frontend QA / UX Engineer)
6. **Graph:** Multimodal Artifact (Video/Image) Ingestion -> DOM/Component Mapping -> CSS/Logic Refactoring -> Visual Re-Verification
7. **Ownership:** Gemini owns the visual fidelity of the application, acting as the eyes of the AI workflow.
8. **Conflicts:** Subjective design interpretations; might conflict with highly customized or non-standard CSS frameworks if not explicitly configured.
9. **Integration:** Can be triggered automatically by a CI/CD pipeline when an end-to-end visual test fails.
10. **Schema:** Component Patches (CSS/TSX) + Before/After visual diff summaries.
11. **Risk:** Misinterpreting compression artifacts or video noise as actual UI bugs.
12. **Verification:** Rerunning the specific Playwright/Cypress visual regression test locally until it reports a 0% pixel variance.
13. **Docs:** Updates the project's internal `DESIGN_SYSTEM.md` if the fix involved creating a new reusable visual pattern.

---

## Campaign 8: Living Documentation Synchronization
**Assigned Model:** Gemini 1.5 Pro
**Primary Command:** `/doc-weaver`

1. **Title:** Continuous Architecture and Code Synchronization
2. **Goal:** Continuously monitor codebase changes and automatically rewrite high-level architecture documents, database schemas, and API documentation to perfectly reflect the current state of the code.
3. **Exit Criteria:** All Markdown files, Mermaid diagrams, and OpenAPI specs accurately represent the `HEAD` of the codebase without manual developer intervention.
4. **Impact:** Eliminates stale documentation. Ensures the "Planning Contracts" and `ARCHITECTURE.md` are always reliable sources of truth for the rest of the multi-agent system.
5. **Roster:** Gemini CLI (Agent: Technical Writer / Systems Analyst)
6. **Graph:** Code Commit Detected -> Diff Analysis -> Impact Assessment on Docs -> Documentation Generation/Update -> Auto-Commit
7. **Ownership:** Gemini owns the consistency between the theoretical design (docs) and the practical implementation (code).
8. **Conflicts:** Developers might manually edit documentation while Gemini is updating it, requiring careful merge conflict handling.
9. **Integration:** Runs as a background loop or git pre-push hook alongside the `/manager` to ensure the project state is always documented.
10. **Schema:** Markdown, Mermaid.js, OpenAPI 3.0, Planning Contracts.
11. **Risk:** Overwriting intentionally abstract documentation with overly verbose, auto-generated code summaries.
12. **Verification:** A linting pass checks that generated API docs match the actual API routes and that Mermaid diagrams render correctly.
13. **Docs:** Maintains a `DOC_SYNC_LOG.md` detailing which files were automatically updated in response to which code changes.
