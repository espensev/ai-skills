---
name: campaign-health
{{#claude}}
description: "Analyze campaign/workflow state for health signals: stuck plans, orphaned agents, stale worktrees, state integrity, and complexity trends. Use when reviewing campaign readiness or recovering blocked multi-agent work."
argument-hint: "<status|stuck|complexity|full> — workflow health check"
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
extracted-from: WinOverSight
portable-since: 2026-03-26
{{/claude}}
{{#codex}}
description: "Analyze campaign/workflow state for health signals: stuck plans, orphaned agents, stale worktrees, state integrity, and complexity trends. Use when reviewing campaign readiness or recovering from blocked work."
{{/codex}}
---

# Campaign Health {{dash}} Workflow State Monitor

Inspects the campaign workflow backend, state store, and planning artifacts for
health signals. Detects stuck plans, orphaned agents, stale worktrees, tracker
drift, and runtime complexity growth.

**All commands run to completion autonomously.**

**Config:** `.{{provider-lc}}/skills/project.toml` {{dash}} paths to state, plans, specs

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `status` | `{{cmd}}campaign-health` or `{{cmd}}campaign-health status` | Quick health summary |
| `stuck` | `{{cmd}}campaign-health stuck` | Find plans/agents stuck in executing/running |
| `complexity` | `{{cmd}}campaign-health complexity` | Analyze workflow runtime size and growth |
| `full` | `{{cmd}}campaign-health full` | All checks with comprehensive report |

Default to `status` if no command given.

---

## Setup: Read Config

Before any command:

1. Read `.{{provider-lc}}/skills/project.toml`
2. Extract `[paths]` {{dash}} state store, plans directory, specs directory, tracker
3. Detect the workflow backend:
   - SQLite DB at `[paths].state` (if `.db` extension)
   - JSON file at `[paths].state` (if `.json` extension)
   - Directory of plan files at `[paths].plans`

4. Extract `[observer].storage` {{dash}} observation file (default: `data/observations.jsonl`)

If no project.toml or paths configured, scan for common locations:
- `data/workflow/campaign.db`, `data/tasks.json`, `data/plans/`
- `data/observations.jsonl` {{dash}} observer storage
- `.{{provider-lc}}/state/`, `docs/agents/`, `docs/campaigns/`

---

## Command: `status` {{dash}} Quick Health Summary

### Steps

1. **State store health**:
   - If SQLite: check file exists, not locked, run integrity check
   - If JSON: check valid JSON, not empty
   - Report: OK / MISSING / CORRUPT / LOCKED

2. **Plan inventory**:
   - Count plans by status: draft, approved, executing, done, failed
   - Flag any in `executing` state > 24h without recent activity

3. **Agent inventory**:
   - Count agents by status: pending, running, done, failed, blocked
   - Flag any in `running` state with no active worktree

4. **Worktree health**:
   - Count active worktrees via `git worktree list`
   - Check each for uncommitted changes
   - Flag orphaned worktrees (not referenced by any agent)

5. **Observation health** (if observer storage exists):
   - Read `[observer].storage` (default: `data/observations.jsonl`)
   - Count total observations, count by status (open/resolved)
   - Count by severity (info/warning/critical)
   - Flag unresolved critical observations

6. **Tracker freshness** (if `[paths].tracker` configured):
   - Check last modified date
   - Flag if > 7 days old with open items

### Report

```
Campaign Health {{dash}} Status

  Backend:     OK (SQLite, 245 KB)
  Plans:       3 total (1 executing, 1 done, 1 draft)
  Agents:      8 total (2 running, 4 done, 1 failed, 1 blocked)
  Worktrees:   2 active (0 dirty)
  Tracker:     Fresh (updated 2h ago)
  Observations: 47 total (12 open)

  Alerts: (none)
```

---

## Command: `stuck` {{dash}} Find Stuck State

### Steps

1. **Stuck plans**: Plans in `executing` state > 24h without agent activity
   - Check agent last-activity timestamps
   - Report plan ID, age, last activity

2. **Stuck agents**: Agents marked `running` with no active worktree
   - Cross-reference agent worktree names with `git worktree list`
   - Report agent name, plan, expected worktree

3. **Orphaned worktrees**: Active worktrees not referenced by any agent
   - List all worktrees, filter out main/primary
   - Check each against agent assignments
   - Report worktree path, branch, age

4. **Orphaned specs**: Agent spec files referencing completed/missing plans
   - Scan specs directory for plan references
   - Check each plan exists and is active
   - Report spec file, referenced plan, plan status

5. **Stale tracker**: Tracker file > 7 days old with open items
   - Parse tracker for open/incomplete items
   - Report item count and age

### Report

```
Campaign Health {{dash}} Stuck Items

  Stuck Plans:
    plan-007 {{dash}} executing for 36h, last agent activity 28h ago
    Recovery: python scripts/task_manager.py plan fail plan-007

  Stuck Agents:
    Agent C (plan-007) {{dash}} running but worktree "wt-agent-c" missing
    Recovery: python scripts/task_manager.py fail C

  Orphaned Worktrees:
    {{wt}}/wt-experiment {{dash}} no agent reference, 5 days old
    Recovery: git worktree remove {{wt}}/wt-experiment

  Orphaned Specs:
    (none)

  Stale Tracker:
    live-tracker.md {{dash}} 12 days old, 3 open items
    Recovery: review and update manually
```

Each stuck item includes an actionable recovery command.

---

## Command: `complexity` {{dash}} Runtime Health

### Steps

1. **Workflow runtime size**: Measure main runtime files
   - Line count of primary backend script(s)
   - Count functions and classes
   - Track thresholds: < 2K lines healthy, 2-5K growing, > 5K needs decomposition

2. **Large functions**: Find functions > 50 lines (top 5 by size)

3. **Import count**: Count imports in main runtime
   - > 30 suggests over-responsibility

4. **Plan complexity**: Analyze recent plans
   - Average agent count per plan
   - Average file ownership entries per plan
   - Max dependency depth

5. **Growth trend**: Compare current metrics against last report (if exists)

### Report

```
Campaign Health {{dash}} Complexity

  Runtime:
    task_manager.py      2,804 lines   [GROWING]
    task_runtime/ (8)    1,200 lines   [HEALTHY]

  Top 5 large functions:
    task_manager.py:execute_plan    82 lines
    task_manager.py:merge_results   67 lines
    ...

  Imports: 24 [HEALTHY]

  Plan complexity (last 5 plans):
    Avg agents: 3.2
    Avg files/agent: 8
    Max dep depth: 2

  Growth: +340 lines since last report (14 days ago)
```

---

## Command: `full` {{dash}} Comprehensive Report

Runs all three checks plus:
- State store integrity (full check, not just exists)
- Plan completion rate (`done / (done + failed)`)
- Agent success rate
- Worktree disk usage
- Observation summary (if observer is active)

Writes report to `docs/artifacts/campaign-health-report.md`.

---

## Integration

| Skill | How Campaign Health Helps |
|-------|--------------------------|
| `{{cmd}}manager` | Campaign-health goes deeper {{dash}} stuck detection, orphan finding |
| `{{cmd}}manager verify` | Include health check in campaign exit criteria |
| `{{cmd}}observer` | Record health findings as `drift` or `debt` observations |
| `{{cmd}}loop` | Good candidate for periodic sweep passes |
| `{{cmd}}planner` | Check health before planning to avoid stacking on stuck plans |

---

## Conventions

- Read project.toml for all project-specific paths
- Never modify state, plans, or specs {{dash}} only report
- Always provide actionable recovery commands for stuck items
- Report all categories even when healthy (visibility)
- Write full reports to docs/artifacts/ for history tracking
