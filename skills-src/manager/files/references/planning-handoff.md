# Planning handoff — surface, feedback, autonomy, and `plan` steps

Manager owns campaign orchestration; the planner skill and the planning
contract own plan design. Do not copy their decomposition rules into manager.

## Planning Surface

Treat `analysis_v2.planning_context` from `analyze --json` as the main planning
input. Consume it in this order:

1. `planning_context.analysis_health`
2. `planning_context.priority_projects`
3. `planning_context.ui_surfaces`
4. `planning_context.ownership_summary`
5. `planning_context.coordination_hotspots`
6. `planning_context.conflict_zones`

If `analysis_health.partial_analysis` or `analysis_health.fallback_only` is
true, plan conservatively around startup projects, packaging projects, shared
UI surfaces, and high-overlap hotspots.

## Feedback Inputs

Use feedback in this order:

1. explicit user correction or requirement change
2. failing build, test, lint, or verify output
3. blocker or regression signals in `data/observations.jsonl` (if present)
4. plan drift between JSON, docs, tracker, and code

Treat single weak signals as local context. Promote repeated or reusable ones
into observation-log records or eval cases so future runs start from better
evidence.

## Autonomous Addition Policy

When running autonomously, you may include extra improvements without asking
only when all of these are true:

- the addition directly supports the requested work or removes waste discovered
  in the same owned surface
- the change stays inside already-owned files or dedicated cleanup/test files
- the change does not widen public API, schema, or configuration surface
- the change adds no new dependency unless it replaces a larger one with a clear
  net simplification
- the change fits the same verification path and does not increase campaign
  scope by more than roughly 25 percent

If any condition fails, keep the idea in the final "suggested follow-ups"
section instead of implementing it.

## `plan` command steps

1. Read the planner skill and planning contract.
2. Run `python scripts/task_manager.py plan preflight --json`; stop on errors.
3. Run `python scripts/task_manager.py plan create "<description>" --json`.
4. Design and register agents using the planner contract and the returned
   `analysis_v2.planning_context`; preserve single-file ownership and explicit
   dependencies.
5. Finalize concrete goal, exit criteria, verification, and documentation
   fields through `task_manager.py plan finalize`.
6. Approve and execute through the backend, then replace every generated spec
   TODO with self-contained instructions before any agent launch.
7. Keep `data/plans/{plan-id}.json` authoritative and write the durable
   `docs/campaign-{plan-id}-{slug}.md` view.
8. Report `status` and `graph`. Under `go`, continue to `run ready`; under
   plan-only invocation, return the ready plan without launching agents.

This section intentionally contains only the manager/backend handoff; detailed
planning policy is loaded on demand from the owning skill and contract.
