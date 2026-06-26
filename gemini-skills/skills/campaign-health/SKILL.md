---
name: campaign-health
description: Analyze campaign/workflow state for health signals — stuck plans, orphaned agents, stale worktrees, state integrity, and runtime complexity trends
---

# Campaign Health Protocol

## Core Mandate
Inspect the campaign workflow backend, state store, and planning artifacts for health signals. Detect stuck plans, orphaned agents, stale worktrees, tracker drift, and runtime complexity growth. Provide actionable recovery commands for every stuck item.

## Execution Rules
1. **Follow the global guardrails in GEMINI.md.** This is a read-only ops skill — it does not gate on the Planning Contract.
2. **Read-only:** Campaign-health never modifies state, plans, or specs. Output is reports and recovery commands only.
3. **Evidence Over Intuition:** Every stuck item must cite the exact state file, agent name, plan ID, or worktree path.
4. **Always offer recovery:** Each FAIL item must include a concrete command the user (or `/manager`) can run to recover.

## Data Sources
Read paths from `[paths]` in project.toml:
- State store — `[paths].state` (SQLite `.db` or JSON `.json`)
- Plans directory — `[paths].plans` (default `data/plans/`)
- Specs directory — `[paths].specs` (default `agents/`)
- Tracker file — `[paths].tracker` (default `live-tracker.md`)
- Observation log — `[observer].storage` (default `data/observations.jsonl`)

If no `[paths]` configured, scan: `data/workflow/campaign.db`, `data/tasks.json`, `data/plans/`, `data/observations.jsonl`.

## Commands
- `/campaign-health status` — quick health summary (default): backend, plans, agents, worktrees, tracker, observations
- `/campaign-health stuck` — find plans/agents stuck in executing/running, orphaned worktrees, stale specs, stale tracker
- `/campaign-health complexity` — analyze workflow runtime size (lines, functions, imports, plan complexity, growth trend)
- `/campaign-health full` — all three plus state-integrity check, completion rate, success rate, disk usage; writes `docs/artifacts/campaign-health-report.md`

## Stuck Detection Heuristics
- **Stuck plan** — `executing` state > 24h with no recent agent activity
- **Stuck agent** — `running` status but `git worktree list` does not show the expected worktree
- **Orphaned worktree** — active worktree not referenced by any agent in any plan
- **Orphaned spec** — `agents/agent-*.md` referencing a completed or missing plan
- **Stale tracker** — `live-tracker.md` > 7 days old with open items

## Output Contract
Emit a structured report with sections for: Backend, Plans, Agents, Worktrees, Tracker, Observations. Always show all sections even when healthy — visibility matters. For each FAIL or WARN item:
- What was found (with exact file/path/ID)
- Why it's flagged (the heuristic that fired)
- Recovery command to run next (concrete, copy-pasteable)

## Recovery Commands
Recovery commands match the backend command surface used by `/manager`:
- **Stuck plan** — `python scripts/task_manager.py plan fail <plan-id>`
- **Stuck agent** — `python scripts/task_manager.py fail <agent>`
- **Orphaned worktree** — `git worktree remove <worktree-path>`
- **Stale tracker** — review and update manually

Exit 0 on healthy/WARN. Exit 1 only on integrity FAIL (corrupt state store, missing required paths).
