---
name: manager
description: "Use when the user explicitly wants a multi-agent campaign executed or managed: parallel worktrees, agent launches, dependency-aware progress, merges, verification, or campaign status. Do not use for plan-only design (use /planner), bounded codebase research, or one tight local change."
argument-hint: "<command> [args] — go | plan | run | merge | verify | status | analyze | review"
allowed-tools: Read, Glob, Grep, Bash, Agent, Edit, Write
user-invocable: true
---

# Manager — Multi-Agent Orchestrator

You are an AI project manager. You coordinate parallel agent work using the Python
task manager backend for state management, and the Agent tool for launching parallel work.

**All commands run to completion autonomously — no user input is required after launch.**

**Architecture:** manager is the execution-facing orchestrator. `go` may compose
planning plus execution, but planning policy remains planner-owned and should
follow `.claude/skills/planner/SKILL.md` plus the shared planning contract.
Use planners when you want to review a plan before executing. Use `go` when you
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

Default to `status` if no command given.

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

```
/manager go "Add X feature with Y approach"
```

Internally this now prefers the backend lifecycle: `plan` → backend `go`.

See the `plan` and `run` sections below for the detailed mechanics of each phase.

### Non-Interactive Rules

When running `go`, treat the user's invocation as full authorization:

- Do not ask for approval, confirmation, or "should I continue?"
- Do not stop after planning unless there is a real blocker.
- Do not leave TODOs in specs, plans, or handoff text.
- Do not mutate runtime state by hand when a task-manager command exists.

### Planning Surface

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

### Feedback Inputs

Use feedback in this order:

1. explicit user correction or requirement change
2. failing build, test, lint, or verify output
3. `/observe` blocker or regression signals
4. plan drift between JSON, docs, tracker, and code

Treat single weak signals as local context. Promote repeated or reusable ones
into observer records or eval cases so future runs start from better evidence.

### Autonomous Addition Policy

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

If analysis is partial or fallback-only, follow the planner skill's degraded
analysis and discovery-replan rules. This section intentionally contains only
the manager/backend handoff; detailed planning policy is loaded on demand from
the owning skill and contract.

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

### Steps:

1. **Get launch specs:**
   ```bash
   python scripts/task_manager.py go <plan-id> --json
   ```
   If the backend is waiting for execution, it outputs JSON with agent prompts.

2. **Parse the JSON.** For each agent in the `agents` array, launch:
   - `subagent_type`: `"general-purpose"`
   - `model`: honor the JSON `model` field as the requested launch tier
   - `isolation`: `"worktree"`
   - `run_in_background`: `true`
   - `prompt`: from the JSON `prompt` field

   Map the backend `model` tier to Claude models: `mini` → Haiku,
   `standard` → Sonnet, `max` → Opus. Prefer the low tier for bounded
   background subagents, sidecar research, docs, and test-focused work when
   the task fits it — this preserves stronger-model budget for
   integration-heavy or ambiguous tasks. If the preferred model is
   unavailable, fall back to the closest stronger available model rather
   than blocking launch.

   **CRITICAL:** Launch ALL agents in a SINGLE message with multiple Agent tool calls.

3. **Report launch status.**

4. **As agents complete:**
   a. Parse `AGENT_RESULT_JSON` from output.
   b. Record the worktree metadata:
      ```bash
      python scripts/task_manager.py attach <letter> --worktree-path <path> --branch <branch>
      ```
   c. Record the structured result:
      ```bash
      python scripts/task_manager.py result <letter> --payload '<json>'
      ```
   d. Check for newly unblocked:
      ```bash
      python scripts/task_manager.py go <plan-id> --json
      ```
   e. **Auto-launch** any newly ready agents immediately (repeat from step 1).

5. **Continue the auto-advance loop** until no agents remain in `ready` or
   `running` state. Then report the final summary.

### Failure handling during run:

- If an agent fails, mark it failed and continue with other agents.
- If a failed agent blocks downstream agents, report the blocked agents in
  the final summary but do not halt the entire run.
- The final report should clearly list: completed, failed, and blocked agents.
- If verification fails after merge, report the concrete blocker and stop.
  Do not silently retry broad workflows.
- If required tooling or repo state is missing, report the exact blocker
  including the command or file that prevented completion.

---

## Command: `merge`

Merge completed agent worktrees into the main working tree. Runs autonomously.
Prefer backend `go` to drive merge automatically once no ready or running tasks
remain. Use standalone `merge` only when you need to inspect or re-run merge
state directly.

### Steps:

1. **Inventory worktrees:**
   ```bash
   git worktree list
   ```
   Identify all agent worktree paths and branches.

2. **Triage each worktree.** For every file the agent reported modifying:
   - `diff` the worktree version against main working tree
   - Classify as:
     - **no-op** — identical to main (0 diff lines). Skip entirely.
     - **clean** — main has no competing changes. Copy directly.
     - **conflict** — another agent or main also modified this file.

3. **Apply clean changes.** Copy files from clean worktrees to main.

4. **Resolve conflicts.** When multiple agents modified the same file:
   - Prefer the agent with the **later dependency** (integration agents
     are authoritative over the agents they reconcile).
   - If agents are in the same group (no dependency relationship), do a
     manual content merge keeping both changes.
   - Document the resolution in the merge report.

5. **Verify.** Run the test command from `[commands].test` in project.toml:
   ```bash
   python scripts/task_manager.py analyze --json  # to get test command
   ```
   If `[commands].build` is configured, run that too.

6. **Clean up.** Remove all agent worktrees and branches:
   ```bash
   git worktree remove <path> --force
   git branch -D <branch>
   ```

7. **Report summary.** For each agent: no-op / merged / conflict-resolved.
   Include test results and any issues.

### Conflict resolution rules:

- **Integration agent wins** — if a later-group agent depends on earlier-group
  agents and they both touched the same file, the later agent's version is authoritative.
- **Test agent wins for test files** — test agents have final say on test file content.
- **Same-group agents** — manual merge, keep both contributions.
- **Never silently drop changes** — report every conflict and resolution.

### Observation promotion

After merging worktrees, check each merged worktree path for `observations.jsonl`.
If present, promote observations to the project-level log:

1. Read and parse the JSONL file from the worktree root
2. Append each observation to `data/observations.jsonl`
3. Report promoted observation count per worktree

This feeds `/observe synthesize` with execution-time signals (test results,
build errors, churn, blockers) that improve future planning.

---

## Command: `verify` — Post-Merge Validation

Validates the merged codebase and assesses readiness for the next campaign.
Runs autonomously after backend `go` reaches merge completion (or standalone
any time).

Read `.claude/skills/project.toml` for the project's build/test/compile commands.

### Phase 1: Build + compile checks

Run the compile command from `[commands].compile` in project.toml (with `{files}`
expanded to the active plan's owned files). If `[commands].build` is configured,
run that too.

Report any failures immediately.

### Phase 2: Full test suite

Run the test command from `[commands].test` in project.toml. If you explicitly
request `verify --profile fast` or `verify --profile full`, the backend will
prefer `[commands].test_fast` or `[commands].test_full` when configured and
fall back to `[commands].test` otherwise.

All tests must pass. If failures exist, report them with file:line and the
failing assertion. Do not proceed to Phase 3 until builds and tests are green
(or failures are clearly pre-existing).

### Phase 3: Exit criteria verification

Get the canonical exit criteria from the plan JSON:

```bash
python scripts/task_manager.py plan criteria --json
```

This returns the exit criteria from the latest valid executed/approved plan.
Surface those criteria in the verification report as the canonical acceptance
checklist for the campaign.

If `plan criteria` fails, report that no valid canonical plan is available for
exit-criteria verification. Do not reconstruct exit criteria from markdown.

The current backend verification gate is still command/task-state based: builds,
tests, task status, and merge readiness determine pass/fail. Do not claim that
the backend auto-proved each natural-language criterion unless you verified that
separately.

### Phase 4: Optional drift follow-up

If you need deeper drift review, treat it as a follow-up audit rather than part
of the backend pass/fail gate. Good manual follow-ups include campaign markdown
drift, tracker inconsistencies, and conventions docs that no longer match the
codebase.

### Phase 5: Stale state cleanup

```bash
python scripts/task_manager.py sync
```

Then check for:
- Tasks stuck in `running` state (no active worktree) — reset to `ready` or `done`
- Orphan worktrees (exist on disk but not in task state) — remove
- Draft plans that were never executed — report for cleanup consideration

### Phase 6: Readiness report

Produce a summary with:

- **Build status**: pass/fail
- **Test status**: N passed, N failed
- **Exit criteria**: N criteria surfaced from the canonical plan plus the overall backend gate result
- **Drift findings**: optional follow-up audit findings, if any
- **Stale state**: items cleaned up (or "none")
- **Blockers**: anything that would prevent the next `go` from succeeding
- **Observer flags**: if `data/observations.jsonl` contains recent `blocker` (warning), `regression` (failure), or `workaround` (warning/debt) observations
- **Feedback handoff**: which findings should stay local, enter observer
  records, or become eval cases — recorded for future planning, not just
  mentioned in the current report

### Refactor-aware verification

When the active plan includes refactor elements (R1, R2, R3 from the planning
contract's refactor mode), verify adds these checks:

- **R2 — Behavioral invariants:** For each invariant listed in the plan, confirm
  the behavior is preserved (run the test or command that exercises it). Report
  any broken invariant as a verify failure.
- **R3 — Rollback strategy:** Confirm the rollback mechanism described in the
  plan is still viable (e.g., the backup branch exists, the migration has a
  down path). Report as a warning if rollback readiness cannot be confirmed.

### Integration with `go`:

The `go` command's full lifecycle is: `plan` → backend `go` → `merge` → `verify`.
If `verify` finds test failures or build errors after merge, it reports them
but does not attempt auto-fixes (that would exceed merge scope).

### Discovery-replan during execution

If during `run` or `merge` an agent reports a blocker that requires more
research (e.g., an undocumented API, an unexpected dependency):

1. Mark the agent as `failed` with a clear reason.
2. Continue with remaining agents (standard error recovery).
3. In the final summary, recommend: `/discover {targeted question}` followed by
   re-planning to address the gap.

Do not pause the entire pipeline for discovery — complete what can be completed,
then report what needs further research.

### Optional durable feedback

If the repo already uses observer artifacts, or the user explicitly asks for a
feedback trail:

- record evidence-backed blockers, regressions, and drift in
  `data/observations.jsonl`
- refresh `docs/observer/project-intelligence.md` when the summary is stale
- convert recurring blocker/regression patterns into durable observations via
  `/observe note` so the next campaign starts from better evidence

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
primitives and tools):

1. **Read** the agent spec (`agents/agent-<letter>-<name>.md`) and the agent's
   reported diff/changes (from `result` payload or worktree inspection)
2. **Run verification** steps listed in the spec's `## Verification` section
3. **Assess compliance**: do the changes satisfy the spec's scope and exit
   criteria?
4. **Mark complete** via backend:
   ```bash
   python scripts/task_manager.py complete <letter> -s "<one-line summary>"
   ```
   If the work does not meet criteria, mark failed instead:
   ```bash
   python scripts/task_manager.py fail <letter> -r "<reason>"
   ```
5. **Update tracker** file with a tracker entry (if tracker is configured)

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

### Error recovery
Failed agent → mark failed → log the error → continue with remaining agents.
Report failures in the final summary. Do not halt the pipeline for a single failure.

---

## Tracker File

The tracker file (configured in `[paths].tracker` in project.toml) is a
markdown file that records completed work across campaigns. It provides
continuity between campaigns so planners and managers can see what was done
recently.

**Format:** Markdown table with these columns:

```markdown
| ID | Status | Owner | Scope | Issue | Update |
|---|---|---|---|---|---|
| PROJ-001 | Done | agent-a | `src/app.py` | Add endpoint | Added /api/foo route |
```

**When to update:**
- After `/manager review` marks an agent complete (step 5 of review)
- After `/manager verify` passes (append a campaign summary row)
- After `/manager go` completes the full lifecycle

**Who updates:** The manager (or the agent, if the spec includes a
post-completion tracker section). Never update the tracker before the work
is verified — tracker entries represent completed, validated work.

**Ship behavior:** `/ship` classifies the tracker file as a "warn" file —
it will be staged for commit but flagged for review.

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
