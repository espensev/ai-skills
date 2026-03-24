---
name: observer
description: "Maintain passive project intelligence in repo-owned artifacts so Codex can record risks, drift, recurring patterns, and recent decisions without changing product code."
---

# Observer

Use this skill when the user wants durable project memory: notes, drift checks,
risk tracking, or a synthesized project-health view that survives across
sessions.

## Scope

- Prefer this skill for passive observation and project-health summaries.
- Prefer `discover` when the goal is bounded pre-change research for one
  question set.
- Prefer `qa` when the user wants test execution or failure triage.
- Prefer `verification-loop` when the goal is release-readiness validation, not
  longitudinal observation.

## Storage

Use repo-owned additive artifacts only:

- `data/observations.jsonl` for append-oriented observation records
- `data/metrics.jsonl` for simple numeric gauges
- `docs/observer/project-intelligence.md` for synthesized summaries

Create these only when the user asks for observer-style tracking or approves
the workflow. Do not assume every repo wants them.

## Observation Types

Use short, stable categories:

- `decision`
- `pattern`
- `drift`
- `risk`
- `progress`
- `question`
- `debt`
- `regression`
- `blocker`

Each observation should capture:

- timestamp
- category
- one-line summary
- optional detail
- related files
- status: `open`, `resolved`, or `stale`
- severity: `info`, `warning`, or `critical`
- confidence when inference is uncertain

## Workflow

1. Decide whether the user wants a one-off snapshot or an ongoing observation
   loop.
2. Read any existing observer artifacts before adding new ones.
3. Gather evidence from durable repo state only:
   - git status and recent history
   - current plans, trackers, and docs
   - TODO or FIXME markers
   - recent verification or test results already present in the repo
4. Record only evidence-backed observations. Deduplicate against still-open
   entries with the same category and summary.
5. When enough observations exist, synthesize them into
   `docs/observer/project-intelligence.md`.
6. Keep the observer additive. It should not modify product code, campaign
   state, or execution state outside its own artifacts.

## High-Signal Feedback

Prefer durable feedback from these sources, in this order:

- explicit user correction or rejection
- build, lint, typecheck, smoke-test, or test failure with concrete output
- repeated workaround or repeated diff-review finding
- drift between plan, docs, and shipped code
- successful fixes that closed a real regression

Treat a single noisy symptom as local context, not durable memory. Promote it
only when it is evidence-backed and likely to change future behavior.

## Promotion Rules

- Record one-off incidents as observations when they explain the current state.
- Promote recurring regressions and blockers into eval pressure with:
  `python scripts/observe_to_eval.py --merge eval/cases/light-skill-cases.json`
- Re-rank which skills need attention with:
  `python scripts/skill_feedback_loop.py --out docs/skill-improvement-report.md`
- Only turn user preference into a reusable pattern after repetition or an
  explicit request to codify it.

## Rules

- Do not invent backend commands that the repo does not implement.
- Do not claim hooks, agents, or slash commands exist unless they are actually
  present in the current package.
- Do not auto-record speculative observations from weak signals.
- Do not replace `discover`, `planner`, `manager`, or `qa`; enrich them.
- When a finding is really a blocking bug or regression, say so explicitly
  rather than burying it in a vague summary.

## Good Fit In This Package

In `codex-skills`, observer is best used as an optional engineering skill that:

- keeps durable notes about package drift and recurring risks
- summarizes cross-session package health
- gives `discover`, `planner`, or `loop-master` richer context when the user
  asks for it
- stays file-based and stdlib-friendly

It is not, in this package, a guaranteed runtime command surface in
`scripts/task_manager.py`.

## Output

Default response shape:

1. current observation state or requested synthesis
2. evidence-backed observations to add or update
3. resulting artifacts changed
4. next useful command or follow-up skill
