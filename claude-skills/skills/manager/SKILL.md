---
name: manager
description: Orchestrate multiple parallel Claude Code agents for any project. Plan multi-agent work, launch parallel agents in worktrees, merge results, and verify builds.
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

Runs all planning phases to completion without user input.

### Phase 1: Load context

1. Read `.claude/skills/project.toml` — project config (paths, commands, modules)
2. Read `.claude/skills/planning-contract.md` — the shared planning contract
3. Read the conventions file specified in `[project].conventions` — project architecture
4. Scan for discovery documents: check `docs/discovery-*.md` for relevant findings

### Phase 2: Preflight

Before autonomous planning, confirm the repo is configured strongly enough for
autonomous verify:

```bash
python scripts/task_manager.py plan preflight --json
```

If preflight reports errors, stop and report the exact blocker.

### Phase 3: Analyze

```bash
python scripts/task_manager.py plan create "<description>" --json
```

This does three things:
1. Runs codebase analysis (file sizes, imports, conflict zones, planning context)
2. Creates a draft plan summary in runtime state and writes the full plan JSON
   to `[paths].plans`
3. Outputs JSON with the plan context + full analysis for you to consume

### Phase 4: Design

Read `.claude/skills/planning-contract.md` — the shared planning contract that
defines the 13 required plan elements, agent spec format, and decomposition
heuristics. The plan you produce must satisfy all 13 elements.

Using the analysis JSON, design the agent breakdown. For each agent, determine:
- **letter** — next available (provided in the plan output)
- **name** — kebab-case descriptive name
- **scope** — one-line description of what this agent does
- **deps** — which other agents must complete first
- **files** — which files this agent will modify (IMPORTANT: minimize overlap)
- **group** — auto-calculated from deps
- **complexity** — low/medium/high

Rules for good decomposition (from the planning contract):
- **File ownership**: Each file should be owned by at most ONE agent. Check
  `analysis_v2.planning_context` first — use `ui_surfaces`, `ownership_summary`,
  `priority_projects`, and `coordination_hotspots` before falling back to raw
  `conflict_zones`. If two agents must touch the same file, make one the owner
  and the other depend on it.
- **Bounded scope**: An agent should need < 300 lines of changes. If more, split.
- **Self-contained specs**: Each agent spec must contain enough detail for an
  agent to execute without asking questions.
- **Test coverage**: If agents add features, include a test agent that depends
  on the feature agents.
- **Agent count**: Prefer 2-6 agents. More than 6 increases coordination cost.

If `planning_context.analysis_health.partial_analysis` or
`planning_context.analysis_health.fallback_only` is true, be more conservative
with decomposition around startup projects, packaging projects, and shared UI
surfaces.

### Phase 5: Register

Add each agent to the draft plan:

```bash
python scripts/task_manager.py plan-add-agent <plan-id> <letter> <name> \
    --scope "..." --deps "..." --files "..." --complexity medium
```

Repeat for each agent.

### Phase 6: Finalize required plan elements

Before approval, fill the required plan elements through the backend instead of
editing the plan artifact by hand:

```bash
python scripts/task_manager.py plan finalize <plan-id> \
    --goal "..." \
    --exit-criterion "..." \
    --verification-step "..." \
    --documentation-update "..."
```

At minimum, ensure the goal statement and exit criteria are concrete. The
backend can synthesize minimum values, but explicit values are preferred.

### Phase 7: Auto-approve + Execute

**Do NOT ask the user for approval.** Approve and execute immediately:

```bash
python scripts/task_manager.py plan approve <plan-id>
python scripts/task_manager.py plan execute <plan-id>
```

This auto-registers all agents in the state file and generates spec template
files in the specs directory.

### Phase 8: Write Plan Artifacts

Keep the machine-readable plan in:

```
data/plans/{plan-id}.json
```

Write the human-readable campaign document to:

```
docs/campaign-{plan-id}-{slug}.md
```

Derive the slug from the campaign title (2-4 words, kebab-case). The JSON
plan file is the authoritative machine-readable source of truth; the markdown
document is the durable human-readable campaign record. `verify` consumes plan
JSON first and uses markdown only for drift checks.

### Phase 9: Fill spec files

**Fill in each spec file** with complete task instructions — never leave TODOs:

For each agent:
1. Read the relevant source files the agent will modify
2. Edit the spec template to replace all TODOs with detailed, actionable instructions
3. Include specific code locations, function names, expected behavior
4. The spec should be self-contained — an agent running it should not need to ask
   any clarifying questions

### Phase 10: Report + proceed

```bash
python scripts/task_manager.py status
python scripts/task_manager.py graph
```

Present the plan document path and a summary of the 13 elements,
then report the ready agents. If invoked via `go`, immediately proceed to
`run ready`. If invoked via `plan` alone, report that agents are ready and
the user can launch with `/manager run ready`.

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
   - `isolation`: `"worktree"`
   - `run_in_background`: `true`
   - `prompt`: from the JSON `prompt` field

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

### Observer-test promotion

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
- Always `isolation: "worktree"` for launches
- Always verify before declaring done
