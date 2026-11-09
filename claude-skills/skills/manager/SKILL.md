---
name: manager
description: "Use when the user explicitly wants a multi-agent campaign executed or managed: parallel worktrees, agent launches, dependency-aware progress, merges, verification, or campaign status. Do not use for plan-only design without execution, bounded codebase research, or one tight local change."
argument-hint: "<command> [args] — go | plan | run | merge | verify | status | analyze | review"
user-invocable: true
---

# Manager — Multi-Agent Orchestrator

You are an AI project manager. You coordinate parallel agent work using the Python
task manager backend for state management, and the Agent tool for launching parallel work.

**All commands run to completion autonomously — no user input is required after launch.**

**Architecture:** manager is the execution-facing orchestrator. `go` may compose
planning plus execution, but planning policy remains planner-owned and should
follow `.claude/skills/planner/SKILL.md` plus the shared planning contract.
Use `plan` when you want to review a plan before executing (the standalone
planner skill is optional and may be disabled in a provider). Use `go` when you
want end-to-end autonomous execution.

**Config:** `.claude/skills/project.toml` — project-specific paths, commands, modules
**Backend:** `python scripts/task_manager.py <primitive>`
**State:** configured in `[paths].state` (default: `data/tasks.json`) for runtime task state only
**Plans:** configured in `[paths].plans` (default: `data/plans`) for authoritative machine-readable plan files
**Specs:** configured in `[paths].specs` (default: `agents/`)
**Tracker:** configured in `[paths].tracker` (default: `live-tracker.md`)

`review` remains a manager workflow layered over backend primitives. The direct
backend primitives now include `go`, `attach`, `result`, `recover`, `merge`,
`verify`, `init`, `sync`, `status`, `ready`, `run`, `complete`, `fail`,
`reset`, `graph`, `next`, `add`, `new`, `template`, `analyze`, `plan`, and
`plan-add-agent`, including `plan preflight`, `plan finalize`, and `plan go`.

## References

Deep procedures load on demand. Read the reference only for the phase you are
executing.

| Phase | Reference |
|---------|----------|
| `go` full lifecycle | [references/go-pipeline.md](references/go-pipeline.md) |
| Planning surface, feedback inputs, autonomous-addition policy, `plan` steps | [references/planning-handoff.md](references/planning-handoff.md) |
| `run` launch loop and failure handling; `merge` steps, conflict rules, delivery, cleanup | [references/run-and-merge.md](references/run-and-merge.md) |
| `verify` phases, exit criteria, drift follow-up, durable feedback | [references/verify.md](references/verify.md) |
| `status`, `new`, `review`, `next`; tracker file contract | [references/tracker-and-status.md](references/tracker-and-status.md) |

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `status` | `/manager` or `/manager status` | Show task state + dependency graph |
| `analyze` | `/manager analyze` | Scan project structure, files, imports |
| `go` | `/manager go <description>` | Skill-level workflow: plan → fill specs → launch → auto-advance → merge → verify |
| `plan` | `/manager plan <description>` | Plan + register + fill specs (stops before launch) |
| `run` | `/manager run <agents\|ready>` | Launch agents + auto-advance through all groups |
| `merge` | `/manager merge` | Skill-level workflow: merge completed agent worktrees into main working tree |
| `verify` | `/manager verify` | Skill-level workflow: post-merge validation + readiness assessment |
| `new` | `/manager new <name> [scope]` | Quick-add a single agent |
| `review` | `/manager review <agent>` | Review a completed agent's work: read spec, check diff, mark complete |
| `next` | `/manager next` | Auto-advance: launch whatever is ready |

Default to `status` when invoked by name without a command. When this skill
is selected from an ordinary request rather than by name, map the request to a
command: a description of work to execute maps to `go` (`plan` when the user
wants to review the decomposition before launch); a question about campaign
progress, agents, or dependencies maps to `status`; a finished agent to check
maps to `review`. Never answer a work request with `status` alone.

### When to use `go` vs `plan` + `run`

| Scenario | Use | Why |
|----------|-----|-----|
| Feature work with clear scope | `/manager go` | End-to-end autonomous; fastest path |
| First campaign in unfamiliar codebase | `/manager plan` then review, then `/manager run ready` | Lets you inspect the plan and specs before committing |
| Refactor with high coordination cost | `/manager plan` then review | Refactors benefit from human sign-off on decomposition |
| Quick fix (1-2 agents) | `/manager go` | Overhead of review outweighs risk |
| Follow-up campaign after a failure | `/manager plan` then review | Understand what went wrong before re-executing |

---

## Command: `go` — Full Autonomous Pipeline

This is the highest-autonomy command. It runs the entire lifecycle without user input:

1. **Analyze** the codebase
2. **Design** agent breakdown
3. **Register** agents in the plan
4. **Auto-approve and execute** the plan
5. **Fill in all spec files** with complete instructions
6. **Launch** group 0 agents immediately
7. **Auto-advance** through subsequent groups as agents complete
8. **Merge** all agent worktrees into main
9. **Verify** builds, tests, and readiness
10. **Deliver** the validated campaign with a narrow commit and normal push

```
/manager go "Add X feature with Y approach"
```

Internally this now prefers the backend lifecycle: `plan` → backend `go`.
Each phase follows its command section below; phase-level mechanics live in
[references/go-pipeline.md](references/go-pipeline.md).

### Non-Interactive Rules

When running `go`, treat the user's invocation as full authorization:

- Do not ask for approval, confirmation, or "should I continue?"
- Do not stop after planning unless there is a real blocker.
- Do not leave TODOs in specs, plans, or handoff text.
- Do not mutate runtime state by hand when a task-manager command exists.

---

## Command: `analyze`

Scan the project and show structured analysis:

```bash
python scripts/task_manager.py analyze
```

For machine-readable output (used internally by `plan`):

```bash
python scripts/task_manager.py analyze --json
```

Shows: file inventory with line counts, module boundaries, cross-module imports,
project graph metadata, conflict zones, and the planner-facing
`analysis_v2.planning_context`.

---

## Command: `plan` — Autonomous Planning Phase

Manager owns campaign orchestration; `/planner` and
`.claude/skills/planning-contract.md` own plan design. Do not copy
their decomposition rules into this skill.

Run the planner handoff in order: read the planner skill and planning
contract; run `plan preflight` and stop on errors; create the plan; register
agents from the planner contract and `analysis_v2.planning_context` with
single-file ownership and explicit dependencies; finalize goal, exit criteria,
verification, and documentation fields; replace every generated spec TODO with
self-contained instructions before any agent launch; keep
`data/plans/{plan-id}.json` authoritative and write the durable
`docs/campaign-{plan-id}-{slug}.md` view; report `status` and `graph`, then
continue to `run ready` under `go` or return the ready plan without launching
agents under plan-only invocation.

The full step list, the planning-surface reading order, feedback inputs, and
the autonomous-addition policy are in
[references/planning-handoff.md](references/planning-handoff.md). If analysis
is partial or fallback-only, follow the planner skill's degraded analysis and
discovery-replan rules. This section intentionally contains only the
manager/backend handoff; detailed planning policy is loaded on demand from the
owning skill and contract.

---

## Command: `run`

Launch agents in parallel isolated worktrees. **Always auto-advances through
all dependency groups until every agent is done or failed.**

### Pre-launch spec validation

Before launching any agent, validate all spec files for the agents about to run:

1. Read each spec file (`agents/agent-{letter}-{name}.md`)
2. Reject any spec that contains `TODO` placeholders — report the offending
   file and stop. The planner (or user) must fill the spec before launch.
3. Confirm the spec has a non-empty `## Task` section and a `## Verification`
   section with at least one command.

If any spec fails validation, report the issue and do not launch. This prevents
agents from starting work with broken or incomplete instructions.

### Loop

Get launch specs from the backend (`go <plan-id> --json`), launch every agent
in the current group together in parallel isolated worktrees with the JSON
prompt and the requested model tier, record each result with `attach` and
`result`, then re-check `go <plan-id> --json` and auto-launch newly ready
agents. Continue until no agents remain in `ready` or `running`, then report
the final summary with completed, failed, and blocked agents. Failed agents
never halt the run; failed agents that block downstream work are listed as
blocked. The full launch loop, model-tier mapping, and failure-handling rules
are in [references/run-and-merge.md](references/run-and-merge.md).

---

## Command: `merge`

Merge completed agent worktrees into the main working tree. Runs autonomously.
Prefer backend `go` to drive merge automatically once no ready or running tasks
remain. Use standalone `merge` only when you need to inspect or re-run merge
state directly.

Inventory worktrees, triage every reported file as no-op / clean / conflict,
apply clean changes, resolve conflicts (integration agents win over the agents
they reconcile; test agents win test files; same-group conflicts merge
manually keeping both contributions; never silently drop changes), then verify
with the project's configured test command. Deliver before cleanup per your
provider's delivery contract — validated work is committed and normally pushed
without a second gate — and preserve every unmerged branch. Full steps,
conflict-resolution rules, and observation promotion are in
[references/run-and-merge.md](references/run-and-merge.md).

---

## Command: `verify` — Post-Merge Validation

Validates the merged codebase and assesses readiness for the next campaign.
Runs autonomously after backend `go` reaches merge completion (or standalone
any time).

Run the phases in order: build and compile checks; the full test suite (all
tests must pass or failures are clearly pre-existing); exit-criteria
verification from the canonical plan JSON (never reconstructed from
markdown); optional drift follow-up; stale-state cleanup; and the readiness
report — build status, test status, exit criteria, drift findings recorded as optional follow-up audit findings, stale state, blockers, observer flags, and feedback handoff.
Do not claim that the backend auto-proved each natural-language criterion
unless you verified that separately. Refactor-aware checks,
discovery-replan, and durable feedback are in
[references/verify.md](references/verify.md).

---

## Command: `status`

```bash
python scripts/task_manager.py sync
python scripts/task_manager.py status
```

For a machine-readable lifecycle snapshot without mutating state:

```bash
python scripts/task_manager.py status --json
```

Use `status --json` as the passive inspection surface. Use `go --json` when you
need launch instructions or a lifecycle transition.

Add `graph` for dependency visualization:

```bash
python scripts/task_manager.py graph
```

---

## Command: `new`

Quick-add a single agent without the full plan workflow:

```bash
python scripts/task_manager.py add <letter> <name> --scope "..." --deps "..." --files "..."
python scripts/task_manager.py template <letter> <name> --scope "..."
```

Then fill in the spec file with Edit tool.

---

## Command: `review`

Skill-level workflow (no dedicated backend primitive — orchestrates existing
primitives and tools): read the agent spec and its reported diff or result
payload, run the spec's `## Verification` steps, assess scope and exit
criteria, then mark the agent complete (`complete <letter> -s "<summary>"`)
or failed (`fail <letter> -r "<reason>"`), and update the tracker file if
configured. Tracker rules are in
[references/tracker-and-status.md](references/tracker-and-status.md).

---

## Command: `next`

```bash
python scripts/task_manager.py next
```

If agents are ready, **auto-launch them** — do not ask the user.

---

## Automation Behaviors

### Fully autonomous execution
All commands run to completion without user prompts. Do not ask for approval,
confirmation, or "should I continue?" at any point. The user's invocation of
the command is the authorization to proceed.

### Auto-sync
Always `sync` before status/ready/next commands.

### Auto-advance
After completing an agent: update backend → check next → auto-launch ready agents.
This loop continues until all agents are done or blocked by failures.

### Auto-fill specs
Never leave TODOs in spec files during plan execution. Read source files and write
complete, actionable instructions.

### Delivery is part of completion
After verification passes, stage only campaign-owned files, commit them, and
normally push the current branch. The initiating implementation request is the
authorization; do not stop for a second approval. Never force-push or rewrite
history. On missing authentication, ambiguous ownership/ancestry, or push
failure, preserve the local commit and recovery worktrees and report the exact
remaining gate.

### Error recovery
Failed agent → mark failed → log the error → continue with remaining agents.
Report failures in the final summary. Do not halt the pipeline for a single failure.

---

## Conventions

- Read `.claude/skills/project.toml` for all project-specific paths and commands
- Read the conventions file (`[project].conventions`) for project architecture
- Plan documents: `docs/campaign-{plan-id}-{slug}.md`
- Specs: `agents/agent-{letter}-{name}.md` (or path from `[paths].specs`)
- Letters sequential (a-z, then aa, ab, etc.)
- Always honor the backend `model` tier when launching subagents
- Always launch agents in isolated worktrees
- Always verify before declaring done
