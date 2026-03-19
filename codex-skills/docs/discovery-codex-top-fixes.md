# Discovery — Codex Top Fixes

**Goal:** Identify the top 1-4 implementation targets in `codex-skills` after reviewing Gemini portability readiness and current Codex runtime drift.
**Date:** 2026-03-17
**Status:** complete
**Recommended next:** `$planner Fix Codex runtime path portability and installed-runtime bootstrap consistency (see docs/discovery-codex-top-fixes.md)`

---

## Questions

1. Where does the Codex runtime contract diverge from the intended `.codex` install layout?
2. Is there evidence of user-visible breakage in the current installed-runtime lifecycle?
3. Which tests, docs, and examples still propagate the wrong provider paths?
4. What are the top 1-4 implementation targets, in priority order?

---

## Findings

### Q1: Where does the Codex runtime contract diverge from the intended `.codex` install layout?

**Answer:** The runtime contract is split. `task_manager.py` loads project config through the runtime helper's `.codex` default, but several init and preflight code paths still hard-code `.claude`.

**Evidence:**
- `scripts/task_manager.py:106-109` — the file header says project config is loaded from `.codex/skills/project.toml`, and `_CONFIG_PATH = _runtime_config_path(ROOT)`.
- `scripts/task_runtime/config.py:7` — `DEFAULT_CONFIG_RELATIVE_PATH = Path(".codex/skills/project.toml")`.
- `scripts/task_runtime/config.py:92` — `config_path(..., ".codex/skills/project.toml")` keeps the helper default on `.codex`.
- `scripts/task_manager.py:1719` — `_preflight_safe_fix()` copies `planning-contract.md` to `ROOT / ".claude" / "skills" / "planning-contract.md"`.
- `scripts/task_manager.py:1739-1740` — `_plan_preflight_payload()` checks `.claude/skills/project.toml` and `.claude/skills/planning-contract.md`.
- `scripts/task_manager.py:2277-2285` — `_build_init_config()` delegates to bootstrap but passes `template_path=ROOT / ".claude" / "skills" / "project.toml.template"`.
- `scripts/task_manager.py:2566-2567` — `cmd_init()` writes config and template paths under `.claude/skills/...`.
- `scripts/task_runtime/merge.py:32` — `candidate_worktree_roots()` still probes `.claude/worktrees` first.

**Implications:**
- The Codex package does not have one authoritative runtime path contract in code.
- Init, preflight, and merge behavior can diverge from what the docs and config helper declare.
- This is the highest-priority implementation area because it affects core lifecycle commands, not just documentation.

### Q2: Is there evidence of user-visible breakage in the current installed-runtime lifecycle?

**Answer:** Yes. The installed-runtime smoke flow is currently failing in `codex-skills`, and the failures all stop at `plan go` because the runtime cannot find a usable `[commands].test`.

**Evidence:**
- `project.toml.template:17-20` — the template explicitly reserves `[commands]` lines for `test`, `test_fast`, and `test_full`.
- `scripts/task_runtime/bootstrap.py:45-51` — Python project detection is designed to prefill `test = "python -m pytest tests/ -q"` when a `tests/` directory exists.
- `scripts/task_runtime/bootstrap.py:344` — bootstrap formatting explicitly pre-fills `[commands].test` when detection succeeds.
- Command run on 2026-03-17:
  `python -m pytest -q tests\test_preflight_hardening.py tests\test_task_manager_portability.py`
- Result from that command: `59 passed, 4 failed`.
- The 4 failing tests are:
  - `tests/test_task_manager_portability.py::TaskManagerPortabilityTests::test_installed_runtime_go_resume_smoke_reuses_merge_after_verify_failure`
  - `tests/test_task_manager_portability.py::TaskManagerPortabilityTests::test_installed_runtime_go_smoke_can_launch_record_merge_and_verify`
  - `tests/test_task_manager_portability.py::TaskManagerPortabilityTests::test_installed_runtime_recover_smoke_reconciles_git_worktree_by_branch`
  - `tests/test_task_manager_portability.py::TaskManagerPortabilityTests::test_installed_runtime_recover_smoke_resets_stale_run_and_relaunches`
- Each failed with the same runtime blocker:
  `Error: Plan preflight failed:`
  `- Config is missing [commands].test; autonomous verify cannot run.`

**Implications:**
- This is not a theoretical portability concern; installed-runtime lifecycle coverage is already red.
- The failing behavior is consistent with the `.codex` load path and `.claude` init/preflight path split.
- Fixing bootstrap/preflight consistency should be ranked ahead of secondary cleanup work.

### Q3: Which tests, docs, and examples still propagate the wrong provider paths?

**Answer:** The wrong provider paths are embedded in the portability test harness, the preflight tests, the ship skill, and the Ollama bridge docs/examples. That means current validation and operator guidance both reinforce the drift.

**Evidence:**
- `tests/test_task_manager_portability.py:174-179` — `_install_runtime()` copies skills and contract files into `install_root / ".claude" / "skills" / ...`.
- `tests/test_task_manager_portability.py:789`, `818`, `846`, `872`, `901`, `938`, `1097`, `1268`, `1319`, `1366`, `1380`, `1403`, `1578`, `1616`, `1788`, `1921` — multiple portability tests build or inspect `.claude/skills/...`.
- `tests/test_preflight_hardening.py:41` — temp project setup creates `self.skills_dir = self.root / ".claude" / "skills"`.
- `tests/test_preflight_hardening.py:66`, `79`, `96` — preflight tests assert against `.claude/skills/planning-contract.md`.
- `skills/ship/SKILL.md:247` — ship skill says `.claude/worktrees/` are agent worktrees.
- `docs/ollama-bridge.md:27` — bridge docs refer to `.claude/worktrees/`.
- `docs/ollama-bridge.md:93` — bridge docs say outputs are written under `.claude/ollama/`.
- `examples/ollama-bridge.ps1:184` — example script uses `.claude/ollama`.
- `examples/ollama-bridge.ps1:195` — example script uses `.claude/worktrees`.

**Implications:**
- The runtime bug is currently shielded by a test harness that installs the wrong path.
- Documentation cleanup is not optional after runtime repair; otherwise the wrong path contract will be reintroduced.
- Worktree and bridge paths need an explicit Codex decision, not piecemeal replacement.

### Q4: What are the top 1-4 implementation targets, in priority order?

**Answer:** The top implementation targets are:

**1. Unify runtime config/bootstrap/preflight paths on one Codex contract.**

**Evidence:**
- `scripts/task_manager.py:1719`
- `scripts/task_manager.py:1739-1740`
- `scripts/task_manager.py:2285`
- `scripts/task_manager.py:2566-2567`
- `scripts/task_runtime/config.py:7`
- `scripts/task_runtime/config.py:92`

**Implications:**
- This is the root fix for the failing installed-runtime lifecycle.
- The preferred implementation is to stop bypassing the runtime config helper and remove local hard-coded provider paths from `task_manager.py`.

**2. Repair portability/install smoke tests so they certify the real Codex layout.**

**Evidence:**
- `tests/test_task_manager_portability.py:174-179`
- `tests/test_task_manager_portability.py:1380`
- `tests/test_task_manager_portability.py:1616`
- `tests/test_preflight_hardening.py:41`
- 4 installed-runtime smoke tests are currently failing in `pytest`.

**Implications:**
- Without this, the package can keep passing path-specific tests that do not match the Codex contract.
- This should run immediately after fix #1 or in parallel if ownership is kept separate.

**3. Normalize worktree and bridge path handling for Codex.**

**Evidence:**
- `scripts/task_runtime/merge.py:32`
- `skills/ship/SKILL.md:247`
- `docs/ollama-bridge.md:27`
- `docs/ollama-bridge.md:93`
- `examples/ollama-bridge.ps1:184`
- `examples/ollama-bridge.ps1:195`

**Implications:**
- This is the next real portability surface after config/bootstrap.
- The open design question is whether Codex should standardize on `.codex/worktrees`, keep a provider-neutral `.worktrees`, or support a migration path for both.

**4. Add a regression guard that centralizes provider path ownership.**

**Evidence:**
- `scripts/task_runtime/config.py:7` and `:92` already provide a Codex-aware path helper.
- `scripts/task_manager.py` still bypasses that helper in multiple direct path literals.
- The workspace now contains `claude-skills`, `codex-skills`, and a new `gemini-skills` adapter, increasing the cost of provider-path drift.

**Implications:**
- This is the hardening change that prevents a fourth provider package from repeating the same copy-and-edit regressions.
- It should stay small: constants or helper accessors, plus regression checks, not a broad runtime rewrite.

---

## Cross-Cutting Analysis

### Constraints
- The runtime under `scripts/` must remain stdlib-only; fixes should not add package dependencies.
- Package docs already establish `.codex/skills/...` as the installed target layout, so implementation should converge on that documented contract rather than rewriting the docs to match the bug.
- The discovery scope should stay focused on Codex path portability and installed-runtime lifecycle health; broader shared-core extraction is follow-on work.

### Risks

| Risk | Likelihood | Impact | Notes |
|------|-----------|--------|-------|
| Runtime path fixes are applied without updating tests | H | H | The suite will continue certifying the wrong install layout or fail for the wrong reason. |
| Worktree path changes break existing local state | M | M | Merge cleanup already probes multiple roots; migration behavior should stay explicit. |
| Provider-hardening expands into a broad abstraction refactor too early | M | M | Fixes 1 and 2 should land before any larger neutral-core cleanup. |

### Open Questions
- Should Codex standardize worktrees under `.codex/worktrees`, keep `.worktrees`, or support both as a migration contract?
- Should the regression guard live as small path helpers in `task_manager.py`, or should all provider-specific path ownership move fully into `task_runtime`?

---

## Recommendation

Ready to plan.

The first campaign should cover fixes **1** and **2** together because they are coupled by the failing installed-runtime smoke tests. Fix **3** is the next bounded follow-on if the first campaign stays within 2-4 agents. Fix **4** should be treated as a small hardening slice after the runtime is green again.

Recommended next command:

`$planner Fix Codex runtime path portability and installed-runtime bootstrap consistency (see docs/discovery-codex-top-fixes.md)`

---

## Appendix

### Targeted verification command

```text
python -m pytest -q tests\test_preflight_hardening.py tests\test_task_manager_portability.py
```

### Current failing test set

- `test_installed_runtime_go_resume_smoke_reuses_merge_after_verify_failure`
- `test_installed_runtime_go_smoke_can_launch_record_merge_and_verify`
- `test_installed_runtime_recover_smoke_reconciles_git_worktree_by_branch`
- `test_installed_runtime_recover_smoke_resets_stale_run_and_relaunches`

### Shared failure message

```text
Error: Plan preflight failed:
- Config is missing [commands].test; autonomous verify cannot run.
```
