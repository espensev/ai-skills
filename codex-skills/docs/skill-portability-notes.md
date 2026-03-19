# Skill Ecosystem Portability Notes

Current portability status for the exported `codex-skills` package.

## Artifact Model

The reusable contract is explicit:

- `data/tasks.json` = runtime task state only
- `data/plans/{plan-id}.json` = authoritative machine-readable full plan
- `docs/campaign-{plan-id}-{slug}.md` = human-readable campaign record

`tasks.json` may cache plan summaries, but it is not the source of truth for the
full campaign plan.

## Planning Surface

The planner-facing analysis model is now explicit:

- `analysis_v2` is the canonical merged analyzer payload.
- `analysis_v2.planning_context` is the preferred planning surface for planner
  and manager workflows.
- top-level analysis fields such as `files`, `project_graph`, and
  `conflict_zones` remain compatibility projections for existing consumers.
- `analysis_summary` in plan JSON is a compact persisted snapshot, not a
  replacement for the full analyzer schema.

Degraded analysis must remain visible through
`planning_context.analysis_health`. Optional providers may fail or be skipped
without breaking the base runtime, but planners should still see that the
result is partial or heuristic-only.

## Package Layout

This package repo stores the export surface in package-root paths such as:

- `README.md`
- `planning-contract.md`
- `plan-schema.md`
- `analysis-schema.md`
- `project.toml.template`
- `scripts/task_manager.py`
- `scripts/analysis/`
- `scripts/task_runtime/`
- `skills/<skill>/SKILL.md`
- `tests/`

These are the files that should be reviewed, tested, and versioned here.

## Installed Target Layout

After vendoring into a consumer repo, the runtime layout moves to target paths:

- `.codex/skills/<skill>/SKILL.md`
- `.codex/skills/planning-contract.md`
- `.codex/skills/project.toml`
- `.codex/skills/project.toml.template`
- `scripts/task_manager.py`
- `scripts/analysis/*.py`
- `scripts/task_runtime/*.py`
- `data/tasks.json`
- `data/plans/`
- `docs/campaign-*.md`
- `agents/agent-{letter}-{name}.md`
- `live-tracker.md`

`README.md` is package documentation. It is not copied into the installed target
tree unless a consumer repo explicitly chooses to vendor it.

## What Is Hardened

- `scripts/task_manager.py` defaults to `status` when invoked with no command.
- Multi-letter agent IDs are supported for allocation (`z -> aa`, `az -> ba`).
- Dependency parsing supports multi-letter IDs in spec files.
- `sync` prunes orphaned stale state while preserving referenced historical
  dependency chains already present in state.
- Duplicate spec IDs fail fast during sync.
- `ready --json` and `run` emit pure JSON without mixed prose.
- Spec templates use `[commands]` from `.codex/skills/project.toml`.
- Tracker integration is optional; templates degrade cleanly when no tracker is
  configured.
- Full plans are written to `data/plans/` and state stores only summaries.
- Plan snapshots now preserve planner-facing `analysis_health` and
  `planning_context`, not only flat file/module counts.
- `init` seeds the `plans` path and creates `data/plans/`.
- The shipped `project.toml.template` is the tokenized template expected by
  `init --force`.

## Documentation Rules

- Package docs must describe package-root files when talking about this repo.
- Runtime docs may describe `.codex/skills/...` paths when talking about the
  installed target repo.
- Do not describe the package `README.md` as if it were installed into the
  target repo runtime tree.
- When describing planning behavior, prefer `analysis_v2.planning_context`
  instead of implying that `conflict_zones` alone are the planning model.

## Example Files

The JSON files under `examples/` are illustrative plan artifacts, not the
package manifest.

- `plan-006-skill-ecosystem.json` is a package-root example and should reference
  package files such as `README.md` and `skills/...`.
- `plan-009` and `plan-011` illustrate runtime plan flows after the package has
  been vendored into a target repo, so `.codex/skills/...` paths are expected
  there.

Examples should not reference files that are absent from both the package and
the installed runtime layout.

## Remaining Gaps

- There is still no installer or distribution wrapper beyond the documented
  copy steps.
- `init` is usable but still non-interactive.
- The nested `.git` in `skills/codex-skills` is an ownership decision, not a
  runtime requirement, and should be handled explicitly before final merge.

## Verification Expectations

Before calling the handoff complete, verify:

- `python -m pytest -q`
- clean-room install using the README copy steps
- `python scripts/task_manager.py init --force`
- `python scripts/task_manager.py analyze --json`

The generated `.codex/skills/project.toml` should contain rendered values, not
template placeholders. When `analysis.mode` is `auto` or `deep`, optional
providers may appear under `analysis_v2.selection.skipped` if the local toolchain
is unavailable; that is expected as long as the base `basic` provider still
applies.
