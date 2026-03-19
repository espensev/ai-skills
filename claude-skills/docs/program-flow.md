# Program Flow

End-to-end lifecycle of a campaign, from analysis through verified delivery.

## Overview

```
analyze ─> plan create ─> plan finalize ─> plan approve ─> plan execute
                                                                │
           ┌────────────────────────────────────────────────────┘
           v
         sync ─> run ready ─> [agents execute in worktrees] ─> result
           │                                                      │
           │       ┌──────────────────────────────────────────────┘
           │       v
           │     merge ─> verify ─> done
           │
           └─ recompute_ready (unblocks next group) ─> run ready ─> ...
```

The `go` command wraps all post-plan steps into a single auto-advancing call.

---

## Phase 1: Analysis

**Command:** `python scripts/task_manager.py analyze [--json]`

```
1. Compute cache key (SHA-256 of all file mtimes + config)
2. If cache hit → return cached analysis
3. If cache miss:
   a. Run basic_provider (always available — heuristic file scan)
   b. Run optional providers (dotnet-cli if available)
   c. Merge provider results into analysis_v2
   d. Synthesize derived views:
      - project_graph (solution/project relationships)
      - dependency_edges (cross-module links)
      - conflict_zones (files that change together)
      - ui_surfaces (startup/shell/packaging surfaces)
      - ownership_summary (file-to-project mapping)
      - planning_context (stable planner-facing bundle)
   e. Cache result to data/analysis-cache.json
4. Emit telemetry (analysis_ms, analysis_json_bytes)
```

**Key data:** The `planning_context` is the primary planner input. It contains
`analysis_health` (confidence, warnings), `coordination_hotspots`,
`priority_projects`, and `ownership_summary`.

---

## Phase 2: Plan Lifecycle

### Create

**Command:** `python scripts/task_manager.py plan create "description"`

```
1. Sync current state (detect existing tasks)
2. Generate plan ID (plan-001, plan-002, ...)
3. Run project analysis (or reuse cache)
4. Create plan dict:
   - status = "draft"
   - empty agents list
   - analysis_summary with planning_context
   - empty plan_elements (13 standard elements)
5. Persist plan JSON → data/plans/plan-NNN.json
6. Persist plan doc → docs/campaign-plan-NNN-slug.md
7. Upsert plan summary in state → data/tasks.json
```

### Add Agents

**Command:** `python scripts/task_manager.py plan-add-agent <plan-id> <letter> <name> --scope "..." --deps "a,b" --files "..." --complexity medium`

```
1. Load plan from file
2. Validate:
   - Letter not already used (in plan or existing tasks)
   - No duplicate file ownership (files claimed by exactly one agent)
   - Dependencies reference valid agent letters
3. Append agent to plan.agents[]
4. Recompute plan groups from dependency depths
5. Persist updated plan
```

### Finalize

**Command:** `python scripts/task_manager.py plan finalize <plan-id>`

```
1. Load plan
2. Auto-fill missing plan_elements:
   - goal_statement (from description)
   - exit_criteria (default lifecycle criteria derived from plan scope and configured verification availability)
   - verification_strategy (compile + test + build commands)
   - conflict_zone_analysis (from planning_context)
   - integration_points (from planning_context)
3. Validate: return errors (blocking) and warnings (non-blocking)
4. Persist updated plan
```

### Approve

**Command:** `python scripts/task_manager.py plan approve <plan-id>`

```
1. Load plan
2. Validate (strict mode — errors block approval)
3. Require at least 1 agent
4. Set status = "approved", approved_at = now
5. Persist
```

### Execute

**Command:** `python scripts/task_manager.py plan execute <plan-id>`

```
1. Load plan (must be "approved")
2. For each agent in plan.agents[]:
   a. Create task record in state["tasks"][letter]
   b. Write agent spec file: agents/agent-{letter}-{name}.md
3. assign_groups(state) — compute parallel execution layers
4. recompute_ready(state) — mark group-0 agents as "ready"
5. Set plan status = "executed"
6. Persist plan + state
```

### Plan Go (combined)

**Command:** `python scripts/task_manager.py plan go <plan-id>`

```
preflight → finalize → approve → execute
(All steps in sequence, fails if any step fails)
```

---

## Phase 3: Task Execution

### State Machine

```
                  ┌─────────────────────────┐
                  │                         │
                  v                         │
  ┌─────────┐  recompute  ┌───────┐  cmd_run  ┌─────────┐
  │ pending │──────────>│ ready │────────>│ running │
  └─────────┘            └───────┘         └────┬────┘
       │                      ^                  │
       │                      │           ┌──────┴──────┐
       v                      │           v             v
  ┌─────────┐            recompute   ┌──────┐     ┌────────┐
  │ blocked │                 │      │ done │     │ failed │
  └─────────┘                 │      └──┬───┘     └────────┘
       ^                      │         │
       └──────────────────────┴─────────┘
                        (unblocks dependents)
```

**Transitions:**
- `pending` → `ready`: all deps are `done` (via `recompute_ready`)
- `pending` → `blocked`: some deps not `done`
- `blocked` → `ready`: all deps become `done`
- `ready` → `running`: `cmd_run` launches agent
- `running` → `done`: `cmd_result` or `cmd_complete`
- `running` → `failed`: `cmd_result` or `cmd_fail`
- any → `pending`: `cmd_reset`

### Sync

**Command:** `python scripts/task_manager.py sync`

```
1. Load state
2. Scan agents/ for agent-{letter}-{name}.md files
3. Parse each spec: extract deps, scope, files, complexity
4. Detect duplicates (error), stale tasks (remove), new specs (add)
5. Preserve historical tasks referenced by active dependencies
6. Parse live-tracker.md for external status updates
7. assign_groups() — dependency depth → parallel group number
8. recompute_ready() — pending/blocked → ready when deps done
9. Save state
```

### Run

**Command:** `python scripts/task_manager.py run ready|all|a,b,c`

```
1. Sync state
2. Resolve target agents:
   - "ready" → all tasks with status=ready
   - "all" → ready + pending
   - "a,b,c" → explicit list
3. For each target:
   - Skip if done/running/blocked (report in "skipped")
   - Validate spec file exists and parses
   - Set status = "running", started_at = now
4. Save state
5. Emit launch JSON:
   {
     "action": "launch",
     "agents": [{
       "id": "a",
       "model": "sonnet",        ← from complexity → model mapping
       "isolation": "worktree",
       "background": true,
       "prompt": "..."           ← built by build_agent_prompt()
     }]
   }
```

The launch JSON is consumed by the Claude Code CLI to spawn agents in
isolated git worktrees.

### Agent Prompt Construction

`build_agent_prompt(task, spec_text, conventions_file)` produces:

```
You are executing an agent task.

RULES:
1. Read CLAUDE.md first for project conventions.
2. Follow the agent spec below exactly — do not exceed scope.
3. Run ALL verification steps listed in the spec before finishing.
4. When done, output a structured result:

AGENT_RESULT_JSON:
{
  "id": "A",
  "name": "agent-name",
  "status": "done",
  "files_modified": [...],
  "tests_passed": 0,
  "tests_failed": 0,
  "issues": [],
  "summary": "..."
}

--- AGENT SPEC START ---
{full spec markdown}
--- AGENT SPEC END ---
```

### Model Selection

```python
complexity → model mapping (configurable in [models] section):

  low    → haiku   (cheapest)
  medium → sonnet  (default)
  high   → opus    (most capable)
```

Override in `project.toml`:
```toml
[models]
low = "haiku"
medium = "sonnet"
high = "opus"
```

### Result Recording

**Command:** `python scripts/task_manager.py result <agent> [<payload-json>] [--payload <payload-json> | --payload-file <path>] [--json]`

```
1. Load state, find task
2. Validate payload.status in {done, failed}
3. Store in task["agent_result"]:
   - status, files_modified, tests_passed, tests_failed
   - issues, summary, worktree_path, branch
4. If done:
   - Set task status = "done"
   - recompute_ready() — may unblock dependents
5. If failed:
   - Set task status = "failed"
6. Save state
```

---

## Phase 4: Merge

**Command:** `python scripts/task_manager.py merge [agents] [--json]`

```
1. Load state + git worktree inventory
2. Filter to done tasks with recorded worktree paths
3. Sort by group (lower group merges first) then by letter
4. For each task:
   a. Match recorded worktree path to live inventory
   b. For each file in agent_result.files_modified:
      - Check ownership conflicts (lower-group agent owns file)
      - Verify file exists in worktree
      - Copy file from worktree → main tree
   c. Record merge status: merged | conflict | noop
5. Update execution_manifest.merge
6. Save state
```

**File ownership rule:** When two agents modify the same file, the agent in the
higher dependency group supersedes the earlier one (its work is assumed to build
on the dependency chain). If two agents in the same or lower group claim the
file, it is flagged as a conflict requiring manual resolution.

Before merging, the runtime creates a `git stash push` backup when git
worktrees are available, or falls back to `.bak` file copies.

---

## Phase 5: Verify

**Command:** `python scripts/task_manager.py verify [plan-id] [--profile default|fast|full] [--json]`

```
1. Recover stale running tasks
2. Resolve the active plan and gather owned files from the plan/task state
3. Load configured commands from [commands]:
   - compile: e.g. "python -m py_compile {files}" → `{files}` expands to plan-owned files
   - build:   e.g. "dotnet build"
   - test / test_fast / test_full depending on `--profile`
4. Run each command in sequence, capture output + exit code
5. Check the overall gate:
   - No failed commands
   - No failed tasks
   - No incomplete tasks
   - No merge blockers
6. Emit the canonical plan criteria plus the command/task gate result:
   { "status": "passed" | "failed", "criteria": [...], "commands": [...], "profile": "..." }
   - criteria are surfaced from plan JSON; they are not independently auto-proved beyond the overall gate
7. Update execution_manifest.verify
```

---

## Phase 6: Go (Full Lifecycle)

**Command:** `python scripts/task_manager.py go [plan-id] [--json] [--poll SECONDS]`

Use one-shot `--json` for machine-readable output. Use `--poll` for human
progress monitoring until the lifecycle reaches a terminal state.

Auto-advances through the lifecycle based on current state:

```
1. Resolve plan (latest or specified)
2. If plan is draft/approved:
   → finalize + approve + execute
3. Recover stale running tasks
4. If tasks are ready:
   → run ready
   → return status="awaiting_results"
5. If tasks are running:
   → return status="awaiting_results" (call go again later)
6. If tasks are blocked/failed:
   → return status="blocked"
7. If all tasks done:
   → merge
   → verify
   → return status="verified" or "verification_failed"
```

The caller (typically the `/manager` skill) invokes `go` repeatedly until it
reaches a terminal state.

---

## Dependency Groups & Parallelism

Groups are computed from dependency depth:

```
Group 0: agents with no dependencies      → all launch in parallel
Group 1: agents depending on group-0 only → launch after group 0 done
Group 2: agents depending on group-1      → launch after group 1 done
...
```

Example:
```
A (no deps)        → Group 0
B (no deps)        → Group 0
C (depends on A)   → Group 1
D (depends on A,B) → Group 1
E (depends on C)   → Group 2
```

Maximum dependency depth: 200 levels. Circular dependencies detected and
rejected at sync time.

---

## Cost Telemetry

Every `run` command tracks model selection per agent:

```python
model_breakdown = {"haiku": 2, "sonnet": 3, "opus": 1}
```

Cost estimation uses per-model pricing:

```python
_MODEL_PRICING = {
    "haiku":  {"input": 1.00,  "output": 5.00},   # per 1M tokens
    "sonnet": {"input": 3.00,  "output": 15.00},
    "opus":   {"input": 5.00,  "output": 25.00},
}
```

`estimate_campaign_savings()` compares tiered model costs vs all-opus baseline
to quantify savings from complexity-based model selection.

---

## Recovery & Error Handling

### Recover

**Command:** `python scripts/task_manager.py recover [--json]`

```
1. Find tasks stuck in "running" with no live worktree
2. Reset stale tasks to pending
3. Report orphan worktrees (worktrees with no matching task)
```

### Reset

**Command:** `python scripts/task_manager.py reset <agent>`

Resets a task to `pending`, clears all result/merge data. `recompute_ready`
then determines if it should immediately become `ready`.

---

## Data Flow Summary

```
project.toml ──────────> task_manager.py ──────────> tasks.json
                              │                         │
agents/*.md ─── sync ─────────┤                         │
                              │                         │
analysis cache ─ analyze ─────┤                         │
                              │                         │
plans/*.json ─── plan ────────┤                         │
                              │                         │
live-tracker.md ─ sync ───────┘                         │
                                                        │
tasks.json ──> run ──> launch JSON ──> Claude Code CLI  │
                                           │            │
                                    [worktree agent]    │
                                           │            │
                                     result JSON ───────┘
                                           │
                                     merge (copy files)
                                           │
                                     verify (run commands)
                                           │
                                        done
```
