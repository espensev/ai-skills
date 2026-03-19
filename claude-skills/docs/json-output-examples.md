# JSON Output Examples

This document shows the JSON output structures for the three most important
task manager commands. Use `--json` on any of these commands to get
machine-readable output instead of human-friendly text.

## `run ready --json` -- Launch Output

Launches all agents whose dependencies are satisfied and returns the launch
manifest.

```bash
python scripts/task_manager.py run ready --json
```

### Output structure

```json
{
  "action": "launch",
  "timestamp": "2026-03-12T10:30:00Z",
  "requested": ["a", "b", "c"],
  "launched": ["a", "b"],
  "skipped": [
    {
      "id": "c",
      "reason": "blocked",
      "pending_deps": ["a"],
      "detail": "Agent C blocked on A"
    }
  ],
  "agents": [
    {
      "id": "a",
      "name": "extract-storage",
      "spec_file": "agents/agent-a-extract-storage.md",
      "isolation": "worktree",
      "background": true,
      "model": "sonnet",
      "prompt": "You are executing an agent task.\n\nRULES:\n1. Read CLAUDE.md first..."
    },
    {
      "id": "b",
      "name": "add-tests",
      "spec_file": "agents/agent-b-add-tests.md",
      "isolation": "worktree",
      "background": true,
      "model": "haiku",
      "prompt": "You are executing an agent task.\n\nRULES:\n1. Read CLAUDE.md first..."
    }
  ]
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | Always `"launch"`. |
| `timestamp` | string | ISO 8601 timestamp of the launch. |
| `requested` | string[] | Agent IDs that were requested for launch (from the argument). |
| `launched` | string[] | Agent IDs that were actually launched (subset of requested). |
| `skipped` | object[] | Agents that were not launched, with reasons. |
| `skipped[].id` | string | Agent letter ID. |
| `skipped[].reason` | string | One of: `"not_found"`, `"already_done"`, `"already_running"`, `"blocked"`, `"invalid_spec"`. |
| `skipped[].pending_deps` | string[] | Present when reason is `"blocked"`. Lists unfinished dependency IDs. |
| `skipped[].errors` | string[] | Present when reason is `"invalid_spec"`. Lists spec validation errors. |
| `skipped[].detail` | string | Human-readable explanation. |
| `agents` | object[] | Full launch record for each launched agent. |
| `agents[].id` | string | Agent letter ID (e.g., `"a"`). |
| `agents[].name` | string | Agent name in kebab-case. |
| `agents[].spec_file` | string | Relative path to the agent spec file. |
| `agents[].isolation` | string | Always `"worktree"`. Agents run in isolated git worktrees. |
| `agents[].background` | boolean | Always `true`. Agents run in the background. |
| `agents[].model` | string | Claude model tier: `"haiku"`, `"sonnet"`, or `"opus"`. Derived from agent complexity via the `[models]` config section. |
| `agents[].prompt` | string | Full prompt text to pass to the Agent tool. Includes the agent spec content and structured result format instructions. |

### How model is resolved

The `model` field is derived from the agent's `complexity` field using the
`[models]` section in `project.toml`:

| Complexity | Default Model |
|------------|---------------|
| `low` | `haiku` |
| `medium` | `sonnet` |
| `high` | `opus` |

If the `[models]` section is absent or contains an invalid value, the
runtime falls back to `"sonnet"`.

## `plan create --json` -- Plan Creation Output

Creates a new draft plan with codebase analysis and returns the full plan
context.

```bash
python scripts/task_manager.py plan create "Add WebSocket support" --json
```

### Output structure

```json
{
  "action": "plan_created",
  "plan": {
    "id": "plan-012",
    "schema_version": 1,
    "artifact_version": 1,
    "created_at": "2026-03-12T10:30:00Z",
    "status": "draft",
    "description": "Add WebSocket support",
    "slug": "add-websocket-support",
    "planner_kind": "planner",
    "source_discovery_docs": [],
    "source_roadmap": "",
    "phase": "",
    "behavioral_invariants": [],
    "rollback_strategy": "",
    "legacy_status": "",
    "next_letter": "a",
    "agents": [],
    "groups": {},
    "conflicts": [],
    "integration_steps": [],
    "plan_doc": "",
    "plan_file": "data/plans/plan-012.json",
    "plan_elements": {
      "campaign_title": "Add WebSocket support",
      "goal_statement": "",
      "exit_criteria": [],
      "impact_assessment": [],
      "agent_roster": [],
      "dependency_graph": [],
      "file_ownership_map": [],
      "conflict_zone_analysis": [],
      "integration_points": [],
      "schema_changes": [],
      "risk_assessment": [],
      "verification_strategy": [],
      "documentation_updates": ["No documentation updates required."]
    },
    "analysis_summary": {
      "total_files": 47,
      "total_lines": 8320,
      "conflict_zones": [],
      "modules": {
        "scripts": 4200,
        "tests": 2100,
        "skills": 1500,
        "docs": 520
      },
      "detected_stacks": ["python"],
      "project_graph": {
        "nodes": ["..."],
        "edges": ["..."]
      },
      "analysis_schema_version": 3,
      "analysis_providers": ["basic"],
      "analysis_health": {},
      "planning_context": {
        "analysis_health": {},
        "priority_projects": {},
        "ui_surfaces": [],
        "ownership_summary": {},
        "coordination_hotspots": [],
        "conflict_zones": []
      }
    }
  },
  "analysis": {
    "totals": {
      "files": 47,
      "lines": 8320
    },
    "modules": {
      "scripts": {"files": 12, "total_lines": 4200},
      "tests": {"files": 8, "total_lines": 2100}
    },
    "conflict_zones": [],
    "detected_stacks": ["python"],
    "project_graph": {},
    "analysis_v2": {
      "schema_version": 3,
      "providers": [{"name": "basic"}],
      "planning_context": {}
    }
  },
  "existing_tasks": {
    "a": {"name": "previous-task", "status": "done"},
    "b": {"name": "another-task", "status": "done"}
  }
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `action` | string | Always `"plan_created"`. |
| `plan` | object | The full plan object as persisted to `data/plans/{plan-id}.json`. |
| `plan.id` | string | Auto-generated plan ID (e.g., `"plan-012"`). |
| `plan.status` | string | Always `"draft"` for newly created plans. |
| `plan.description` | string | The description passed to the create command. |
| `plan.slug` | string | Kebab-case slug derived from the description. |
| `plan.next_letter` | string | Next available agent letter (accounts for existing tasks). |
| `plan.agents` | object[] | Empty array for new plans. Populated by `plan-add-agent`. |
| `plan.plan_file` | string | Relative path where the plan JSON is stored. |
| `plan.plan_elements` | object | The 13 required plan elements (see planning contract). Initially mostly empty; filled by `plan finalize`. |
| `plan.analysis_summary` | object | Compact snapshot of the codebase analysis, embedded in the plan for planner reference. |
| `plan.analysis_summary.planning_context` | object | The primary planning surface from `analysis_v2`. Contains analysis health, priority projects, UI surfaces, ownership summary, coordination hotspots, and conflict zones. |
| `analysis` | object | Full analysis output, not persisted in the plan. Use this for detailed decomposition decisions during planning. |
| `analysis.totals` | object | `files` and `lines` counts across the project. |
| `analysis.modules` | object | Per-module file count and line count. |
| `analysis.conflict_zones` | string[] | Declared conflict zones from config or analysis. |
| `analysis.analysis_v2` | object | The canonical machine-facing analysis payload with `planning_context`. |
| `existing_tasks` | object | Map of existing task IDs to their name and status. Helps the planner avoid duplicate work. |

### Plan lifecycle after creation

A newly created plan is in `draft` status. The typical progression is:

```
draft -> (add agents) -> (finalize) -> approved -> executed
```

Or use `plan go` to run finalize + approve + execute in one step.

## `plan criteria --json` -- Exit Criteria Output

Returns the canonical exit criteria for the currently active plan. `verify`
surfaces these as the acceptance checklist alongside its command/task gate.

```bash
python scripts/task_manager.py plan criteria --json
```

### Output structure

```json
{
  "plan_id": "plan-012",
  "status": "executed",
  "plan_file": "data/plans/plan-012.json",
  "plan_doc": "docs/campaign-plan-012-add-websocket-support.md",
  "legacy_status": "",
  "valid": true,
  "criteria": [
    "All WebSocket endpoints respond to ping/pong frames",
    "Existing HTTP API tests pass without modification",
    "New integration test covers WebSocket connection lifecycle",
    "No regressions in the full test suite"
  ]
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `plan_id` | string | ID of the plan whose criteria are being returned. |
| `status` | string | Current plan status (usually "executed", "approved", or "partial"). |
| `plan_file` | string | Relative path to the plan JSON file. |
| `plan_doc` | string | Relative path to the human-readable campaign markdown document. |
| `legacy_status` | string | Non-empty only for plans migrated from an older format. |
| `valid` | boolean | Always `true` when criteria are successfully resolved. |
| `criteria` | string[] | List of exit criteria strings. Each is a concrete, verifiable condition that must be satisfied for the campaign to be considered complete. |

### How plan resolution works

When called without `--plan-id`, the command finds the latest valid plan
that is in `executed`, `partial`, or `approved` status. If no such plan exists, the
command fails with an error message explaining why no plan could be resolved.

When called with a specific plan ID:

```bash
python scripts/task_manager.py plan criteria plan-012 --json
```

It loads that exact plan and returns its criteria regardless of status.

### Where criteria come from

Exit criteria are populated in two places during the plan lifecycle:

1. **At creation** -- the `plan_elements.exit_criteria` array is initially
   empty.
2. **At finalization** -- the `plan finalize` command accepts
   `--exit-criterion` flags (repeatable) that populate the array.

The `verify` command reads criteria from the plan JSON (via
`plan criteria --json`) and includes them in its verification report. The
current backend gate does not independently prove each natural-language
criterion; it reports the command/task-state gate result and surfaces the
canonical checklist alongside it.

## Common Patterns

### Piping JSON to other tools

The documented one-shot `--json` commands emit valid JSON written to stdout.
You can pipe them to `jq` or other tools:

```bash
python scripts/task_manager.py status --json | jq '.counts'
python scripts/task_manager.py plan criteria --json | jq '.criteria[]'
```

### Using JSON output in skill workflows

Skills like `/manager` and `/planner` consume JSON output programmatically:

```bash
# Get launch instructions
python scripts/task_manager.py run ready --json
# Parse the agents array and launch each via the Agent tool

# Check if campaign is complete
python scripts/task_manager.py plan criteria --json
# Compare criteria against codebase state
```

### Other commands with `--json` support

Beyond the three commands documented above, these also support `--json`:

| Command | JSON payload summary |
|---------|---------------------|
| `status --json` | Full lifecycle state: project name, plan ID, status, counts by state, agents grouped by status, launch/merge/verify records, next action recommendation. |
| `ready --json` | Lists ready and blocked agents with dependency details. |
| `verify --json` | Post-merge verification result: overall pass/fail, surfaced criteria checklist, command results, warnings, failed/incomplete tasks, and merge blockers. |
| `go --json` | One-shot lifecycle result for the current phase: plan, recovery, and launch or merge/verify payloads depending on state. |
| `plan show --json` | Full plan object including all elements and analysis summary. |
| `plan list --json` | Array of plan summaries (ID, status, description, agent count, timestamps). |
| `plan preflight --json` | Readiness check: errors, warnings, configured commands. |
| `plan validate --json` | Validation errors and warnings for a specific plan. |
| `plan finalize --json` | Finalization result: updated fields, validation status, errors, warnings. |
| `plan go --json` | Combined preflight + finalize + approve + execute result. |
| `analyze --json` | Full codebase analysis with file inventory, modules, conflict zones, and `analysis_v2.planning_context`. |




