# Planning handoff — surface, feedback, autonomy, and `plan` steps

Use the project’s `.codex/skills/planning-contract.md` for the 13 required plan elements, agent spec format and decomposition rules.

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
UI surfaces, and high-overlap hotspots. Name missing inventory and ownership
data in the risk assessment. Inspect shared files and use explicit file lists
before assigning concurrent writers. When an unresolved dependency prevents
safe planning, use `discover` for that question and resume from its evidence.

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

1. Read the planning contract, project conventions, and any cited discovery findings.
2. Run `python scripts/task_manager.py plan preflight --json`. Resolve reported errors before proceeding.
3. Run `python scripts/task_manager.py plan create "<description>" --json`. Use the returned plan ID and planning context for subsequent commands.
4. Register each agent with `python scripts/task_manager.py plan-add-agent <plan-id> <letter> <name> --scope "..." --files "..." --complexity medium`. Add `--deps "..."` for dependencies. Assign exclusive file ownership per group.
5. Run `python scripts/task_manager.py plan finalize <plan-id> --goal "..." --exit-criterion "..." --verification-step "..." --documentation-update "..."`. Repeat flags for additional criteria, checks or documentation updates.
6. Run `python scripts/task_manager.py plan approve <plan-id>`, then `python scripts/task_manager.py plan execute <plan-id>`. These commands register runtime tasks and generate specs. Fill all spec TODOs before launch.
7. Keep the JSON plan under the configured plans directory authoritative and write the derived `docs/campaign-{plan-id}-{slug}.md`. For phased refactors, include R1–R3 from the contract.
8. Report `status` and `graph`. Return the prepared plan for a plan-only request. Under `go`, continue with the launch instructions from `go <plan-id> --json`.
