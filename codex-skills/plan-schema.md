# Plan Schema — Version 1

## Overview

This document defines the JSON schema for campaign plans as implemented
by `scripts/task_manager.py`. The plan JSON file at
`data/plans/{plan-id}.json` is the single authoritative artifact for a
campaign's structure and state.

## Schema Version

Every plan JSON file includes `schema_version` and `artifact_version`
fields at the top level. Both are currently `1`. Plans loaded without
these fields receive `1` as a default via `_default_plan_fields()`.

## Top-Level Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string | yes | — | Plan identifier (`"plan-001"`, `"plan-002"`, ...) |
| `schema_version` | integer | yes | `1` | Schema version |
| `artifact_version` | integer | yes | `1` | Artifact format version |
| `created_at` | string | yes | — | ISO 8601 datetime |
| `approved_at` | string | no | `""` | ISO 8601 datetime, set on approval |
| `executed_at` | string | no | `""` | ISO 8601 datetime, set on execution |
| `updated_at` | string | yes | — | ISO 8601 datetime, set on every write |
| `status` | enum | yes | `"draft"` | `draft`, `approved`, `executed`, `rejected`, `partial` |
| `description` | string | yes | `""` | Campaign description |
| `slug` | string | yes | — | Kebab-case slug derived from description (2-4 words) |
| `planner_kind` | enum | yes | `"planner"` | `planner`, `planner-refactor`, `manager-go` |
| `source_discovery_docs` | array of string | no | `[]` | Paths to discovery documents consulted |
| `source_roadmap` | string | no | `""` | Path to refactor roadmap |
| `phase` | string | no | `""` | Phase identifier for multi-phase refactors |
| `behavioral_invariants` | array of string | no | `[]` | Behaviors that must not change (refactor plans) |
| `rollback_strategy` | string | no | `""` | How to revert the campaign (refactor plans) |
| `legacy_status` | string | no | `""` | `"needs_backfill"` for pre-enforcement plans |
| `backfill_reasons` | array of string | no | `[]` | Why this plan was marked legacy |
| `next_letter` | string | no | `""` | Next available agent letter at plan creation |
| `agents` | array | yes | `[]` | Agent roster |
| `groups` | object | yes | `{}` | Map of group number (string key) to agent letter arrays |
| `conflicts` | array of string | no | `[]` | Free-text conflict notes |
| `integration_steps` | array of string | no | `[]` | Free-text integration notes |
| `plan_file` | string | yes | — | Relative path to the JSON plan file |
| `plan_doc` | string | yes | — | Relative path to the campaign markdown document |
| `plan_elements` | object | yes | — | The 13 contract-defined plan elements |
| `analysis_summary` | object | no | — | Codebase analysis snapshot at plan creation |

## Agent Object

Each entry in the `agents` array:

| Field | Type | Required | Description |
|---|---|---|---|
| `letter` | string | yes | Sequential identifier (`a`-`z`, then `aa`, `ab`, ...) |
| `name` | string | yes | Kebab-case descriptive name |
| `scope` | string | yes | One-line scope starting with a verb |
| `deps` | array of string | yes | Agent letters this agent depends on; `[]` if none |
| `files` | array of string | yes | Files this agent creates or modifies |
| `group` | integer | yes | Execution group: `0` if no deps, else `1 + max(group of deps)` |
| `complexity` | enum | yes | `low`, `medium`, `high` |

## Plan Elements Object

The `plan_elements` field contains the 13 elements defined by the
planning contract. These are populated by planners and auto-refreshed
from agent data by `_refresh_plan_elements()`.

| Field | Type | Content |
|---|---|---|
| `campaign_title` | string | Campaign title |
| `goal_statement` | string | One-paragraph goal |
| `exit_criteria` | array of string | Testable completion conditions. Each entry is a plain string (no checkbox prefix); the markdown renderer adds `- [ ]` formatting for the human-readable campaign document. |
| `impact_assessment` | array of object | `{file, lines, change_type, risk}` |
| `agent_roster` | array of object | Auto-populated from `agents` |
| `dependency_graph` | array of object | `{group, agents}` — auto-populated from `groups` |
| `file_ownership_map` | array of object | `{file, owner}` — auto-populated from agents |
| `conflict_zone_analysis` | array | Conflict zone records |
| `integration_points` | array of string | Cross-agent contracts |
| `schema_changes` | array of string | Migration details, or empty |
| `risk_assessment` | array of object | `{risk, likelihood, impact, mitigation}` |
| `verification_strategy` | array of string | Verification commands and checks |
| `documentation_updates` | array of string | Required doc changes |

Auto-populated fields (`agent_roster`, `dependency_graph`,
`file_ownership_map`) are refreshed from agent data on every plan
write. The remaining fields are set by the planner and preserved
across updates.

Default values: `verification_strategy` defaults to the commands from
`[commands]` in `project.toml`. `documentation_updates` defaults to
`["No documentation updates required."]`.

## Analysis Summary Object

Captured at plan creation and preserved for reference:

| Field | Type | Description |
|---|---|---|
| `total_files` | integer | Files in the project |
| `total_lines` | integer | Total source lines |
| `conflict_zones` | array | `{files, reason}` from config or auto-discovery |
| `modules` | object | Category name to total line count |
| `detected_stacks` | array of string | Heuristic stack markers such as `dotnet`, `wpf`, `winui`, `cpp`, `xaml-ui` |
| `project_graph` | object | Project/solution graph snapshot with `nodes` and `edges`, including startup/package metadata when detected |
| `analysis_schema_version` | integer | Version of the nested analyzer schema used to create the snapshot |
| `analysis_providers` | array of string | Provider names that contributed to the snapshot, such as `basic` |
| `analysis_health` | object | Planner-facing provider health, degraded-analysis flags, and confidence from `analysis_v2.planning_context.analysis_health` |
| `planning_context` | object | Planner-facing merged snapshot including conflict zones, UI surfaces, ownership summary, and coordination hotspots |

## Validation Rules

### Draft (plan create)

- All top-level fields present with defaults
- `status` is `"draft"`
- `agents` may be empty
- `plan_elements` may have empty fields
- No content quality checks

### Agent addition (plan-add-agent)

- Letter unique within the plan and not in task state
- Dependencies reference existing agent letters within the plan
- Groups auto-assigned from dependency depth
- Ownership validation runs in non-strict mode (warnings only)

### Contract validation (plan validate)

Returns structured output with `errors` (blocking) and `warnings`
(advisory).

Errors:
- Empty `campaign_title`
- Empty `goal_statement`
- Empty `exit_criteria`
- Empty `verification_strategy`
- Empty `documentation_updates`
- Duplicate agent letters
- Unknown dependency references
- Dependency cycles
- Duplicate file ownership (same file claimed by multiple agents)
- `verification_strategy` not referencing the configured test command

Warnings:
- Plan marked as legacy (`needs_backfill`)
- Empty `impact_assessment`, `conflict_zone_analysis`, or
  `risk_assessment`
- Empty `integration_points`
- Configured `compile` or `build` commands not in verification strategy
- Referenced discovery docs or roadmap files not found on disk

### Approval (plan approve)

Runs contract validation in strict mode. Rejects if any errors exist.
Requires at least one agent.

### Execution (plan execute)

- Requires `approved` status; refuses `draft` plans
- Re-runs contract validation
- Registers agents in task state
- Generates spec templates for missing spec files
- Transitions status to `executed`

## Spec Template

Backend-generated templates include:
- `## Exit Criteria` section with defaults from agent scope and plan
- `## Verification` section with commands from `[commands]`
- `## Context` section referencing the conventions file
- `## Constraints` section with test command reference
- `## Post-completion` section for tracker updates (when configured)

Templates contain no `TODO` placeholders. A spec is considered
incomplete if `_spec_has_placeholders()` detects any `TODO`, `[agent]`,
`Details here.`, or other template markers.

`cmd_run()` validates specs before launch and skips agents with
incomplete or missing specs.

## Markdown Rendering

`_render_plan_doc(plan)` converts plan JSON to the campaign document at
`docs/campaign-{plan-id}-{slug}.md`. Structural sections 1-12 are
rendered from `plan_elements`. Sections R1-R3 are appended when refactor
metadata is present (`phase`, `behavioral_invariants`,
`rollback_strategy`).

Rendering is triggered by `_persist_plan_artifacts()`, which is called
on every plan mutation: create, add-agent, approve, reject, execute.

If a rendered markdown document diverges from the current plan JSON,
the JSON is authoritative and the markdown is re-rendered on next
mutation.

## Legacy Migration

Plans loaded without enforcement-era fields receive defaults via
`_default_plan_fields()`. Plans with empty required elements that have
a non-draft status are marked `legacy_status: "needs_backfill"` with
specific reasons listed in `backfill_reasons`.

Legacy marking is non-destructive — plans are preserved as-is with
metadata added. The `_resolve_plan_for_verify()` function first checks
`execution_manifest.plan_id` to prefer the actively executing plan,
then falls back to scanning for the most recent valid
executed/approved/partial plan. In both paths, plans that fail
validation are skipped, so legacy plans do not interfere with the
verify pipeline.

## Example

```json
{
  "id": "plan-008",
  "schema_version": 1,
  "artifact_version": 1,
  "created_at": "2026-03-11T18:00:00+00:00",
  "approved_at": "2026-03-11T18:05:00+00:00",
  "executed_at": "2026-03-11T18:05:30+00:00",
  "updated_at": "2026-03-11T18:10:00+00:00",
  "status": "executed",
  "description": "Add WebSocket live push",
  "slug": "add-websocket-live-push",
  "planner_kind": "planner",
  "source_discovery_docs": ["docs/discovery-websocket.md"],
  "source_roadmap": "",
  "phase": "",
  "behavioral_invariants": [],
  "rollback_strategy": "",
  "legacy_status": "",
  "backfill_reasons": [],
  "next_letter": "c",
  "agents": [
    {
      "letter": "a",
      "name": "add-ws-handler",
      "scope": "Add WebSocket handler module with connection management",
      "deps": [],
      "files": ["ws_handler.py"],
      "group": 0,
      "complexity": "medium"
    },
    {
      "letter": "b",
      "name": "wire-ws-routes",
      "scope": "Wire WebSocket routes into app.py",
      "deps": ["a"],
      "files": ["app.py"],
      "group": 1,
      "complexity": "low"
    }
  ],
  "groups": {
    "0": ["a"],
    "1": ["b"]
  },
  "conflicts": [],
  "integration_steps": [],
  "plan_file": "data/plans/plan-008.json",
  "plan_doc": "docs/campaign-plan-008-add-websocket-live-push.md",
  "plan_elements": {
    "campaign_title": "Add WebSocket live push",
    "goal_statement": "Replace HTTP polling with WebSocket push for dashboard data streams.",
    "exit_criteria": [
      "All source files compile without errors",
      "Test suite passes with zero failures",
      "WebSocket endpoint accepts connections"
    ],
    "impact_assessment": [
      {"file": "app.py", "lines": 450, "change_type": "modify", "risk": "high"},
      {"file": "ws_handler.py", "lines": null, "change_type": "create", "risk": "low"}
    ],
    "agent_roster": [
      {"letter": "a", "name": "add-ws-handler", "scope": "Add WebSocket handler", "deps": [], "files": ["ws_handler.py"], "group": 0, "complexity": "medium"},
      {"letter": "b", "name": "wire-ws-routes", "scope": "Wire WebSocket routes", "deps": ["a"], "files": ["app.py"], "group": 1, "complexity": "low"}
    ],
    "dependency_graph": [
      {"group": 0, "agents": ["a"]},
      {"group": 1, "agents": ["b"]}
    ],
    "file_ownership_map": [
      {"file": "ws_handler.py", "owner": "a"},
      {"file": "app.py", "owner": "b"}
    ],
    "conflict_zone_analysis": [],
    "integration_points": ["Agent a creates ws_handler.py; agent b imports and registers routes"],
    "schema_changes": [],
    "risk_assessment": [
      {"risk": "Browser compatibility", "likelihood": "low", "impact": "medium", "mitigation": "Use standard WebSocket API"}
    ],
    "verification_strategy": [
      "python -m py_compile ws_handler.py app.py",
      "python -m pytest tests/ -q"
    ],
    "documentation_updates": ["Add WebSocket module to architecture table in AGENTS.md"]
  },
  "analysis_summary": {
    "total_files": 42,
    "total_lines": 12500,
    "conflict_zones": [
      {"files": ["app.py", "static/index.html"], "reason": "endpoint-fetch coupling"}
    ],
    "modules": {"core": 5000, "frontend": 3000, "tests": 2000},
    "detected_stacks": [],
    "project_graph": {"nodes": [], "edges": []},
    "analysis_schema_version": 3,
    "analysis_providers": ["basic"],
    "analysis_health": {"mode": "basic", "confidence": "medium", "warnings": []},
    "planning_context": {}
  }
}
```
