# Planning Contract: Gemini Multi-Agent Adapter v1.0 Finalization

1. **Title:** Finalizing the Experimental Gemini CLI Adapter
2. **Goal:** Resolve remaining structural inconsistencies between the campaign blueprints, portability rules, and registered command wrappers.
3. **Exit Criteria:**
    - All 7 generic skills (`discover`, `planner`, `manager`, `qa`, `ship`, `loop`, `loop-master`) have corresponding `.toml` wrappers and `.md` instructions.
    - All 4 specialized Gemini skills (`epic-refactor`, `forensic-debugger`, `ui-test-engineer`, `doc-weaver`) are fully registered.
    - `GEMINI.md` portability rules are consistent with the final file system state.
4. **Impact:** Provides a complete, ready-to-use template for installing these skills in any repository.
5. **Roster:** Gemini CLI (Agent: Lead Architect / Manager)
6. **Graph:** `docs/system-map.md` -> `/planner` -> `docs/planning-contract.md` -> `/ship` (Final Wrappers) -> `/qa` (Final Check)
7. **Ownership:** Manager owns the loop; Ship Agent (Gemini) implements the missing `.toml` and `.md` files.
8. **Conflicts:** None identified; repo is isolated.
9. **Integration:** Plugs into the existing global `GEMINI.md` guardrails.
10. **Schema:** Standard `.toml` for command registration; Markdown for persona instructions.
11. **Risk:** Minimal, as this project is docs-first and does not include an active Python runtime yet.
12. **Verification:** Recursive file system scan to confirm all 11 commands (7 generic + 4 special) are present.
13. **Docs:** Final update to `README.md` to declare v1.0 completion.

---

### Task List
- **Task 1.1:** Register `/loop` and `/loop-master` command wrappers.
- **Task 1.2:** Write persona instructions for `/loop` and `/loop-master`.
- **Task 1.3:** Synchronize `GEMINI.md` portability notes with the final command list.
- **Task 1.4:** Final QA verification pass.

---

### Outcome and Verification

- **Status**: PASSES
- **Verification Performed**: 
  - `list_directory` scans of `.gemini/commands` and `docs/instructions` confirmed that all 14 required skill wrappers (`brief`, `discover`, `doc-weaver`, `edit`, `epic-refactor`, `forensic-debugger`, `guardrails`, `loop`, `loop-master`, `manager`, `planner`, `qa`, `ship`, `ui-test-engineer`) and their corresponding `.md` instruction files are fully present.
  - Review of `GEMINI.md` and `README.md` indicates full alignment with the v1.0 release. `README.md` has been updated to reflect the implementation of `/loop` and `/loop-master`.
- **Conclusion**: The structural inconsistencies have been resolved, and the file system matches the planned target state for the generic and specialized skills.
