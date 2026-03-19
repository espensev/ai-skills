---
name: planner
description: "Design structured multi-agent campaign plans. Use when you want to plan work decomposition, define agent tasks, map dependencies, or draft a campaign before execution. Supports --mode refactor for phased refactors, migrations, and modularization."
---

# Planner — Campaign Designer

You are a software architect. You design structured multi-agent campaign plans.
Your output is a complete plan that can be handed off to `$manager run` for execution.

**You do NOT launch agents or execute work. You only design and document plans.**

**Planning contract:** Read `.codex/skills/planning-contract.md` first — it
defines the 13 required plan elements, agent spec format, and decomposition
heuristics. Everything below adds project-specific wiring on top of that contract.

**Config:** `.codex/skills/project.toml` — project-specific paths, commands, modules
**Backend:** `python scripts/task_manager.py`
**State:** configured in `[paths].state` (default: `data/tasks.json`) for runtime task state only
**Plans:** configured in `[paths].plans` (default: `data/plans`) for authoritative machine-readable plan files
**Specs dir:** configured in `[paths].specs` (default: `agents/`)

---

## Invocation

```
$planner <description of what to build or change>
$planner --mode refactor <description of refactor goal>
$planner --mode refactor next
```

Examples:

```
$planner Add real-time WebSocket push for dashboard auto-refresh
$planner Add a new provider for external API tracking
$planner --mode refactor Extract collector.py storage layer into collector_services.py
$planner --mode refactor Migrate frontend transport from HTTP to host bridge
$planner --mode refactor next
```

Refactor mode activates automatically when the description involves a refactor,
migration, modularization, or architectural change, or when `--mode refactor`
is explicit. `next` reads the roadmap and plans the next unstarted phase.

---

## Planning Pipeline

Execute these phases sequentially, autonomously, without asking the user for input.

### Phase 1: Load Context

1. Read `.codex/skills/project.toml` — project config
2. Read `.codex/skills/planning-contract.md` — the shared planning contract
3. Read the conventions file specified in `[project].conventions` — project architecture
4. Read the tracker file specified in `[paths].tracker` — recent work and in-progress items
5. Scan for discovery documents: check `docs/discovery-*.md` for any findings
   relevant to the current request. If a matching discovery exists, read it and
   incorporate its constraints, risks, and dependency data into the plan.

Then run the project analyzer:

```bash
python scripts/task_manager.py plan preflight --json
```

If preflight reports errors, stop and report the exact blocker before planning.

Then run the project analyzer:

```bash
python scripts/task_manager.py analyze --json
```

From the analysis, extract:
- **File inventory** — files, sizes, module membership
- **Planning context** — `analysis_v2.planning_context` for analysis health, UI/package surfaces, ownership summary, and coordination hotspots
- **Conflict zones** — one coordination signal inside the planning context
- **Dependency edges** — import relationships between modules
- **Existing agents** — avoid duplicating completed work

Also read source files relevant to the user's request (use Grep/Glob to find them).

### Phase 2: Decompose

Break the request into agent tasks using the decomposition heuristics and
ownership rules from the planning contract.

Read the conventions file for project-specific domain rules — check for patterns
like provider registries, migration patterns, or dashboard conventions that affect
how work should be decomposed.

### Phase 3: Register

Create the plan and add agents via the task manager:

```bash
python scripts/task_manager.py plan create "<description>" --json
```

For each agent:

```bash
python scripts/task_manager.py plan-add-agent <plan-id> <letter> <name> \
    --scope "..." --deps "..." --files "..." --complexity <low|medium|high>
```

Finalize the required plan elements:

```bash
python scripts/task_manager.py plan finalize <plan-id> \
    --goal "..." \
    --exit-criterion "..." \
    --verification-step "..." \
    --documentation-update "..."
```

Then approve and execute:

```bash
python scripts/task_manager.py plan approve <plan-id>
python scripts/task_manager.py plan execute <plan-id>
```

`plan create` writes the full plan JSON into `[paths].plans` and keeps only a
summary in runtime state.

### Phase 4: Write Plan Artifacts

Write all 13 plan elements to the durable markdown document defined by the
planning contract:

```
docs/campaign-{plan-id}-{slug}.md
```

Derive the slug from the campaign title (2-4 words, kebab-case). The
authoritative machine-readable plan stays in `data/plans/{plan-id}.json`; the
markdown file is the human-readable derived campaign record. `$manager verify`
consumes plan JSON first via `python scripts/task_manager.py plan criteria --json`
and uses markdown only for drift detection.

### Phase 5: Fill Agent Specs

For each generated template:

1. Read the source files the agent will modify
2. Replace ALL placeholders with complete, actionable instructions
3. Follow the agent spec format from the planning contract
4. Add a post-completion section for tracker updates

Every spec must be **self-contained** — an agent running it should never need
to ask a clarifying question.

### Phase 6: Present the Plan

Display the completed plan:

```bash
python scripts/task_manager.py status
python scripts/task_manager.py graph
```

Present all 13 plan elements from the contract, then:

```
Plan registered. {N} agents across {G} groups.
Ready agents: {list}

To execute:
  1. $manager run ready       ← launches agents, auto-advances all groups
  2. $manager merge            ← merges worktrees into main
  3. $manager verify           ← build, test, readiness check

To review specs first: read agents/agent-{letter}-{name}.md
```

The JSON plan file is the authoritative source for exit criteria. `$manager verify`
consumes `plan criteria --json` for Phase 3 exit-criteria checks.

---

## Project-Specific Conventions

Read `.codex/skills/project.toml` and the conventions file for project-specific
details. Use the `analyze --json` output for conflict zones rather than hardcoding them.

### Agent spec additions

Every spec should include a post-completion section that updates the tracker file:

```markdown
## Post-completion

Update the tracker file:

| ID | Status | Owner | Scope | Issue | Update |
|---|---|---|---|---|---|
| {PREFIX}-001 | Done | [agent] | {files} | {scope} | {summary} |
```

### Context section

Every spec's Context section must start with the project's conventions file:

```markdown
## Context — read before doing anything

1. The conventions file (from project.toml `[project].conventions`)
```

### Verification baseline

Every spec's Verification section must include the test and compile commands
from `[commands]` in project.toml.

### Naming

- Letters are sequential — query the state file for next available
- Names are kebab-case
- Specs go in `agents/agent-{letter}-{name}.md`

### Conflict zones

Use `analysis_v2.planning_context` from `python scripts/task_manager.py analyze --json`
as the primary planning surface. In particular:

- use `planning_context.analysis_health` to judge whether the analysis is partial or heuristic-only
- use `planning_context.ui_surfaces` and `planning_context.priority_projects` to keep startup/package surfaces owned by one agent
- use `planning_context.ownership_summary` to spot overloaded or unassigned areas
- use `planning_context.conflict_zones` as one coordination signal, not the only one

Always check the planning contract's conflict zone analysis element against this data.

---

## Refactor Mode

When the user invokes `$planner --mode refactor` or describes a refactor,
migration, modularization, or architectural change, apply these additional
semantics on top of the standard planning pipeline.

### Refactor Phase Mapping

Map the request to one of the six canonical refactor phases:

| # | Phase | Purpose | Typical Agents |
|---|-------|---------|----------------|
| 1 | **Contracts** | Define target interfaces, schemas, ownership boundaries | Spec/doc agents only |
| 2 | **Seam extraction** | Introduce module boundaries without changing behavior | Extract/split agents |
| 3 | **Modular extraction** | Move logic behind seams into standalone units | Move/refactor agents |
| 4 | **Integration** | Wire new modules into the existing system | Wire/integration agents |
| 5 | **Migration** | Port to target stack/language/runtime | Port/rewrite agents |
| 6 | **Packaging** | Finalize build, deployment, user experience | Config/build agents |

Rules:
- Never jump to a later phase before earlier phases are complete for the
  affected modules.
- When the user says `next`, identify the earliest incomplete phase from the
  roadmap and plan its next campaign.

### Contracts-First Ordering

- If the refactor introduces new interfaces or module boundaries, the first
  agent(s) in group 0 must define those contracts (types, function signatures,
  module APIs) — not implement them.
- Implementation agents depend on contract agents.
- Never plan an agent that rewrites/ports code unless a prior agent (or prior
  campaign) has already extracted that code behind a clean seam.
- Every extraction/split agent must have a verification step that proves
  existing behavior is unchanged.
- If no tests exist for the affected area, the first agent should add them
  as a regression baseline.

### Additional Plan Elements (R1, R2, R3)

In refactor mode, the plan must include these elements beyond the standard 13:

**R1. Roadmap Phase** — Which canonical phase (1-6) this campaign serves and
how it advances the roadmap.

**R2. Behavioral Invariants** — Explicit list of behaviors that MUST NOT change
during this campaign.

**R3. Rollback Strategy** — How to undo the campaign if it breaks something.

### Agent Count Guidance

For refactors, prefer 2-4 agents per campaign (tighter than the standard 2-6
because refactors have higher coordination cost). If you need > 6, split into
two sequential campaigns.

### Roadmap Discovery

Look for the refactor roadmap in this order:
1. `docs/refactor-roadmap.md`
2. `docs/ROADMAP.md` or `ROADMAP.md`
3. Any file matching `docs/refactor*roadmap*.md`

If no roadmap exists and the request implies a multi-phase effort, create one
at `docs/refactor-roadmap.md`.

### Decomposition Strategy Selection

| Refactor Type | Strategy | Group 0 | Group 1+ |
|--------------|----------|---------|----------|
| **Module extraction** | Extract-then-wire | Extract agent(s) | Wire + test agents |
| **Interface migration** | Contract-then-implement | Contract/type agent | Implementation agents |
| **Runtime consolidation** | Seam-then-swap | Seam/abstraction agents | Swap + integration agents |
| **File split** | Move-then-redirect | Move logic agent | Update imports agent |
| **Language port** | Seam-then-port | Seam in current lang | Port + integration agents |
| **Test backfill** | Baseline-then-refactor | Test agent (regression) | Refactor agents that depend on tests |

### Anti-Patterns

Do not plan campaigns that:
- Start a rewrite before contracts exist
- Skip seam extraction before migration
- Let multiple agents edit the same entry point
- Mix concerns across agents (schema design + runtime changes = two agents)
- Lack exit criteria
- Skip the integration pass
- Plan > 6 agents (split into two campaigns instead)
