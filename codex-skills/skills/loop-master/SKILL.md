---
name: loop-master
description: Supervise multi-round Codex execution for a larger objective. Use when the user wants you to coordinate repeated loops, route work between discover/planner/manager/qa/ship, or structure safe parallel work across multiple rounds.
---

# Loop Master

Use this skill when the work is too large or ambiguous for a single local loop but does not yet justify ad hoc orchestration.

## Responsibilities

- Define the current round objective and done condition.
- Decide what stays local versus what should be delegated or researched.
- Keep the immediate blocker on the coordinator path.
- Limit parallel work to a small number of disjoint tracks.
- Reconcile results between rounds before launching the next one.

## Routing Guidance

- Use `loop` for the coordinator's immediate implementation step.
- Use `discover` for bounded unknowns that should be answered before planning or editing.
- Use `planner` when the repo needs a durable multi-agent campaign design.
- Use `manager` when the project already uses `scripts/task_manager.py` and the plan should be executed through that runtime.
- Use `qa` for round-end validation and regression checks.
- Use `ship` when validated work needs staging or commit packaging.

## Parallelism Rules

- Keep the immediate critical-path task local.
- Spawn sidecar work only when scopes are disjoint and materially useful.
- Prefer two through four workstreams at most.
- Collapse overlapping work instead of creating competing owners.

## Round Structure

For each round:

1. State the objective.
2. Identify the local blocker.
3. Assign optional sidecar workstreams.
4. Define validation gates.
5. Decide whether to continue, replan, or stop.

## Output Contract

Produce a short round plan with:

- objective
- local_blocker
- delegated_workstreams
- ownership
- validation_gates
- stop_condition
