# Implementation Checklist

Verify each item after backend edits are merged. Items are grouped by
the ticket that delivers them. Check the box when the behavior is
confirmed working.

Schema reference: `plan-schema.md` (v1)

---

## 1. Backend CLI Surface

### Plan lifecycle commands

- [x] `plan create "<desc>" --json` returns draft JSON with all top-level fields
- [x] `plan-add-agent <id> <letter> <name> --scope --deps --files --complexity` adds agent to draft
- [x] `plan validate <id> --json` returns `{ valid, errors, warnings }`
- [x] `plan approve <id>` transitions status `draft` → `approved` on success
- [x] `plan approve <id>` rejects with `TaskManagerError` on invalid plan
- [x] `plan execute <id>` transitions status `approved` → `executed`
- [x] `plan execute <id>` refuses unapproved plans
- [x] `plan criteria --json` returns exit criteria from latest valid plan
- [x] `plan criteria <id> --json` returns exit criteria for a specific plan

### State and agent commands

- [x] `run <agents|ready> --json` returns JSON with agent prompts
- [x] `run` blocks agents with incomplete specs (reason: `invalid_spec`)
- [x] `complete <letter> -s "<summary>"` marks agent done
- [x] `fail <letter> -r "<reason>"` marks agent failed
- [x] `next` returns newly unblocked agents
- [x] `sync` reconciles state with worktree reality
- [x] `analyze --json` returns file inventory, conflict zones, imports

---

## 2. Plan JSON Schema (v1)

### Top-level fields present in draft output

- [x] `id` (string, e.g. `"plan-001"`)
- [x] `schema_version` = `1` (integer)
- [x] `artifact_version` = `1` (integer)
- [x] `created_at`, `updated_at` (ISO 8601 string)
- [x] `approved_at`, `executed_at` (ISO 8601 string, default `""`)
- [x] `status` (enum: `draft` / `approved` / `executed` / `rejected` / `partial`)
- [x] `description` (string)
- [x] `slug` (kebab-case, derived from description)
- [x] `planner_kind` (enum: `planner` / `refactor-planner` / `manager-go`)
- [x] `source_discovery_docs` (array of string)
- [x] `source_roadmap` (string, default `""`)
- [x] `agents` (array of agent objects)
- [x] `groups` (object, string keys → arrays of agent letters)
- [x] `conflicts`, `integration_steps` (arrays of string)
- [x] `plan_file`, `plan_doc` (relative paths)
- [x] `plan_elements` (object with 13 contract elements)
- [x] `analysis_summary` (object)

### Agent object fields

- [x] `letter` (string, sequential: a-z, then aa, ab, ...)
- [x] `name` (string, kebab-case)
- [x] `scope` (string, one-line starting with verb)
- [x] `deps` (array of string, `[]` if none)
- [x] `files` (array of string)
- [x] `group` (integer, auto-calculated from deps)
- [x] `complexity` (enum: `low` / `medium` / `high`)

### Plan elements object

- [x] `campaign_title` (string)
- [x] `goal_statement` (string)
- [x] `exit_criteria` (array of string)
- [x] `impact_assessment` (array of `{file, lines, change_type, risk}`)
- [x] `agent_roster` (auto-populated from agents)
- [x] `dependency_graph` (auto-populated from groups)
- [x] `file_ownership_map` (auto-populated from agents)
- [x] `conflict_zone_analysis` (array)
- [x] `integration_points` (array of string)
- [x] `schema_changes` (array of string)
- [x] `risk_assessment` (array of `{risk, likelihood, impact, mitigation}`)
- [x] `verification_strategy` (array of string, defaults from `[commands]`)
- [x] `documentation_updates` (array of string)

### Refactor metadata (flat top-level fields)

- [x] `phase` (string, e.g. `"2 — Seam extraction"`)
- [x] `behavioral_invariants` (array of string)
- [x] `rollback_strategy` (string)
- [x] Refactor fields round-trip through JSON persistence

### Sentinel value discipline

- [x] `deps` uses `[]` not `"—"` or `"none"`
- [x] Optional strings default to `""` not `null`
- [x] Optional arrays default to `[]`

---

## 3. Draft Validation (plan create)

- [x] All top-level fields present with defaults via `_default_plan_fields()`
- [x] `status` set to `"draft"`
- [x] `agents` may be empty
- [x] `plan_elements` may have empty fields
- [x] No content quality checks enforced at draft stage

---

## 4. Agent Addition Validation (plan-add-agent)

- [x] Letter unique within the plan
- [x] Dependencies reference existing agent letters within the plan
- [x] Groups auto-assigned from dependency depth
- [x] Ownership validation runs in non-strict mode (warnings only)

---

## 5. Semantic Validation (plan validate)

### Errors (blocking)

- [x] Empty `campaign_title` → error
- [x] Empty `goal_statement` → error
- [x] Empty `exit_criteria` → error
- [x] Empty `verification_strategy` → error
- [x] Empty `documentation_updates` → error
- [x] Duplicate agent letters → error
- [x] Unknown dependency references → error
- [x] Dependency cycles → error
- [x] Duplicate file ownership (same file claimed by multiple agents) → error
- [x] `verification_strategy` not referencing configured test command → error

### Warnings (advisory, non-blocking)

- [x] Plan marked as legacy (`needs_backfill`) → warning
- [x] Empty `impact_assessment`, `conflict_zone_analysis`, or `risk_assessment` → warning
- [x] Empty `integration_points` → warning
- [x] Configured `compile` or `build` commands not in verification strategy → warning
- [x] Referenced discovery docs or roadmap files not found on disk → warning

### Output structure

- [x] `cmd_plan_validate()` returns JSON with `valid`, `errors`, `warnings`
- [x] Exit code 1 when errors present, 0 when valid

---

## 6. Approval Validation (plan approve)

- [x] Calls `_validate_plan(strict=True)` — rejects if any errors
- [x] Warnings reported but do not block approval
- [x] Requires at least one agent
- [x] Raises `TaskManagerError` on failure (plan stays `draft`)

---

## 7. Execution Preconditions (plan execute)

- [x] Refuses plans not in `approved` status
- [x] Re-runs semantic validation
- [x] Registers agents in task state
- [x] Generates spec templates for missing spec files
- [x] Transitions status to `executed`
- [x] Sets `executed_at` timestamp

---

## 8. Spec Template Generation

- [x] `_render_spec_template()` generates complete spec with no TODOs
- [x] Template includes `## Exit Criteria` section with defaults from agent scope
- [x] Template includes `## Verification` section with commands from `[commands]`
- [x] Template includes `## Context` section referencing conventions file
- [x] Template includes `## Constraints` section with test command reference
- [x] `_spec_has_placeholders()` detects `TODO`, `[agent]`, `Details here.`
- [x] `_validate_spec_file()` checks exit criteria presence and placeholder absence
- [x] `cmd_run()` skips agents with incomplete or missing specs

---

## 9. Markdown Rendering

- [x] `_render_plan_doc()` produces structured markdown from plan JSON
- [x] `_persist_plan_artifacts()` writes both JSON and markdown on every mutation
- [x] Slug derived from description (2-4 words, kebab-case)
- [x] Structural sections 1-12 rendered from `plan_elements`
- [x] R1-R3 sections appended when refactor metadata present
- [x] Rendering triggered by: create, add-agent, approve, execute
- [x] JSON is authoritative — markdown re-rendered on next mutation if diverged

---

## 10. Ownership Enforcement

- [x] Each file should be owned by at most one agent
- [x] Duplicate file claims → validation error in strict mode
- [x] `file_ownership_map` auto-populated from agents on every plan write
- [x] Non-strict mode (agent addition) produces warnings only

---

## 11. JSON-First Verify

- [x] `plan criteria --json` exposes exit criteria from plan JSON
- [x] `_resolve_plan_for_verify()` skips plans with empty exit criteria
- [x] Returns `None` when all executed plans are invalid
- [x] Manager SKILL.md Phase 3 consumes `plan criteria --json`
- [x] Markdown absence is not a blocker for exit-criteria verification
- [x] Markdown mismatch reported as drift, not treated as source loss

---

## 12. Legacy Migration

- [x] `_default_plan_fields()` adds missing fields with type-appropriate defaults
- [x] `_mark_plan_needs_backfill()` marks incomplete executed plans
- [x] Backfill reasons list specific empty fields (e.g. `"empty goal_statement"`)
- [x] Draft plans skip backfill marking
- [x] Already-marked plans preserve existing `backfill_reasons` (idempotent)
- [x] Valid executed plans skip backfill marking
- [x] Legacy marking is non-destructive — plans preserved as-is with metadata added

---

## 13. Data Authority Invariants

- [x] `data/plans/{plan-id}.json` is canonical; never overridden by markdown or state
- [x] `docs/campaign-*.md` is derived; re-renderable from JSON without data loss
- [x] `data/tasks.json` is runtime state only; never authoritative for plan structure
- [x] Auto-populated plan elements refreshed from agent data on every write

---

## Test Coverage

| Test file | Count | Coverage |
|---|---|---|
| `tests/test_plan_lifecycle.py` | 22 | Validation gates, approval/execute enforcement, spec templates, legacy migration, resolver, rendering |
| `tests/test_task_manager.py` | 48 | TOML parsing, config loading, state persistence, plan lifecycle, analysis, multi-stack providers |
| `tests/test_task_manager_portability.py` | 36 | Multi-letter IDs, spec parsing, sync pruning, duplicate rejection, JSON output, plan persistence |
| `tests/test_skill_docs_contract.py` | 6 | Skill doc structure, frontmatter validation |
| `tests/test_cli_commands.py` | 21 | CLI commands (sync, status, add, complete, fail, reset, graph, next), error paths (path traversal, corrupt state, missing plans, duplicate agents, dependency cycles) |
| `tests/test_planning_context_plan_lifecycle.py` | 11 | Planning context integration |

All 144 tests passing.

---

## Ticket → Checklist Mapping

| Ticket | Sections |
|---|---|
| 1. Plan validation gate | 1, 3, 4, 5, 6, 7 |
| 2. Canonical artifact persistence | 9, 13 |
| 3. Spec template compliance | 8 |
| 4. JSON-first verify | 11 |
| 5. Legacy migration | 12 |
| 6. Refactor metadata | 2 (refactor fields) |
| 7. Tests | Test Coverage table |
