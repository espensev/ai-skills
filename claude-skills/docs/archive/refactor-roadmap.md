# Cost Optimization — Follow-Up Roadmap

## Context

The first pass (2026-03-12) added model tiering and telemetry. This roadmap
addresses gaps, integration issues, and missing test coverage found during
review.

## Phase 1: Data Integrity (Critical)

**Goal:** Ensure `complexity` flows correctly through every task creation and
normalization path so model selection never falls back silently.

### Findings

1. **`_normalize_task_fields` (task_manager.py:448)** — `complexity` is missing
   from the `setdefault` block. Existing tasks loaded from JSON state files
   will not have the field, causing `resolve_model_for_task` to always default
   to `"medium"` → `"sonnet"`.

2. **`sync_state` inline dict (execution.py:190-204)** — the fallback task dict
   (when `new_task_factory` is None) does not include `complexity`.

3. **`sync_state` preserved history (execution.py:216-232)** — historical tasks
   missing `complexity` defaulting.

4. **`cmd_add` fallback dict (execution.py:816-830)** — inline task dict in the
   else-branch does not include `complexity`.

5. **`cmd_add` via `new_task_factory` (execution.py:804-814)** — does not pass
   `complexity` from args (there is no `--complexity` arg on the `add` CLI
   command).

---

## Phase 2: Test Coverage (High Priority)

**Goal:** Add direct test coverage for all new code paths.

### Missing Tests

1. **`resolve_model_for_task`** — no tests. Need:
   - Default mapping (no config)
   - Config override
   - Missing/empty complexity field
   - Unknown complexity value
   - Empty `[models]` config section

2. **`telemetry.py`** — no tests. Need:
   - `StepTimer` context manager
   - `build_telemetry_payload` with various arg combos
   - `measure_json_bytes` correctness
   - `estimate_agent_cost_usd` per model
   - `estimate_campaign_savings` with mixed models
   - Edge: empty agent list, unknown model

3. **`cmd_run` model field** — the existing `test_cmd_run_json_is_pure_json`
   test asserts on `payload["agents"][0]["id"]` and `prompt` but does NOT check
   for the new `model` field. Must assert it appears and has correct value.

4. **`complexity` in plan execute → task state** — no test verifies that
   `plan-add-agent --complexity high` results in `task["complexity"] == "high"`
   after `plan execute`.

5. **Telemetry in analyze JSON** — no test checks `analyze --json` output
   includes `telemetry` key.

6. **Telemetry in verify JSON** — no test checks verify output includes
   `telemetry` key.

---

## Phase 3: Skill Integration (Medium)

**Goal:** Ensure all skill documents that launch agents or reference complexity
are aware of model tiering.

### Gaps

1. **`planner/SKILL.md`** — mentions `--complexity` in the register command but
   does not explain that complexity now drives model selection and cost. Planners
   should be cost-aware when choosing complexity ratings.

4. **Bootstrap fallback (bootstrap.py:194-253)** — the inline fallback config
   string does NOT include the `[models]` section. Projects initialized without
   a template file will have no `[models]` config, silently falling back to
   hardcoded defaults. This is acceptable behavior but should be documented.

---

## Phase 4: Polish (Low)

### Items

1. **`verify_timer` usage** — uses manual `__enter__`/`__exit__` instead of
   `with` statement. Harmless but inconsistent with the `cmd_analyze` path
   which uses `with`. Should be refactored to `with` for consistency.

2. **`cost_estimate` only on launch path** — `_go_assess_status` adds
   `cost_estimate` and `telemetry` only when agents are launched, not on the
   merge+verify or blocked paths. The merge+verify path should aggregate final
   telemetry from all steps.

3. **Model validation** — `resolve_model_for_task` does not validate that the
   model string is one of `{"haiku", "sonnet", "opus"}`. A typo in
   `[models]` config (e.g., `low = "haku"`) would silently pass through to
   the Agent tool which may reject it.

4. **Pricing constants** — `_MODEL_PRICING` in `telemetry.py` has a comment
   saying "Updated from public Anthropic pricing as of 2025-05" but includes
   Claude 4.5/4.6 model names (`haiku`, `sonnet`, `opus`) without version
   suffixes. This is fine for estimates but should note it's approximate.
