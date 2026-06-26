---
name: worktree-preflight
description: "Validate planned agent file ownership against dirty worktrees, missing worktrees, stale branches, uncommitted changes, and parallel-agent overlaps before launching a multi-agent campaign."
---

# Worktree Preflight - Pre-Launch Conflict Prevention

Before launching a multi-agent campaign, validates that no two agents' file
ownership lists overlap with each other or with uncommitted changes in active
worktrees, that every agent's target worktree exists, and that worktree
branches are not dangerously stale. Prevents wasted agent runs and complex
post-merge conflict resolution.

**All commands run to completion autonomously.**

**Config:** `.codex/skills/project.toml` - paths and conflict zones

---

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `check` | `$worktree-preflight` or `$worktree-preflight check` | Full preflight: active worktrees, missing/stale worktrees, and overlaps against the pending plan |
| `plan` | `$worktree-preflight plan <plan-id>` | Validate a specific plan's file ownership |
| `dirty` | `$worktree-preflight dirty` | Fast path: report only dirty worktrees, no plan analysis |

Default to `check` if no command given.

---

## Setup: Read Config

Before any command:

1. Read `.codex/skills/project.toml`
2. Extract `[paths].plans` - plan file directory
3. Extract `[conflict-zones]` - known high-risk file pairs
4. Extract `[worktree-preflight].stale-threshold` - commits-behind-base limit for the stale-branch check (default: 50)
5. Detect plan format:
   - JSON plans at `[paths].plans/*.json`
   - Markdown plans with agent tables

---

## Command: `check` - Active Worktree Conflict Scan

### Steps

1. **Inventory active worktrees**:
   ```bash
   git worktree list --porcelain
   ```
   Parse: path, branch, HEAD commit for each.

2. **Check each worktree for dirty files**:
   ```bash
   git -C <worktree-path> diff --name-only
   git -C <worktree-path> diff --cached --name-only
   git -C <worktree-path> diff --name-only HEAD
   ```
   Collect all modified/staged/untracked files per worktree.

3. **Load pending plan ownership**:
   - Find the latest plan in `executing` or `approved` state
   - Extract agent file ownership lists from the plan
   - If no active plan, report "no pending plan" and exit

4. **Cross-reference dirty files against agent ownership**:
   - For each dirty file in each worktree, check if any agent owns it
   - Flag conflicts where a worktree has uncommitted changes in an agent's
     ownership scope

5. **Check agent-to-agent overlap**:
   - For agents that will run in parallel (same dependency group), verify
     no file ownership overlap
   - Overlap between sequential agents (dependency edges) is OK - the later
     agent is authoritative

6. **Check for missing target worktrees**:
   - For each agent whose plan declares a target worktree, verify that
     worktree exists in the `git worktree list` inventory
   - Flag any agent whose target worktree is absent as CONFLICT

7. **Check for stale branches**:
   ```bash
   git -C <worktree-path> rev-list --count <base>..HEAD
   git -C <worktree-path> rev-list --count HEAD..<base>
   ```
   - Compute how many commits each worktree branch is behind base
   - If behind base by more than `[worktree-preflight].stale-threshold`
     commits (default 50), flag as WARNING (advisory rebase)

### Report

```
Worktree Preflight - Check

  Active Worktrees:
    wt-frontend  - 3 dirty files
    wt-backend   - clean
    main         - 1 dirty file

  Pending Plan: plan-012 (4 agents, 2 groups)

  Conflicts:
    CONFLICT: wt-frontend has uncommitted changes in:
      src/components/Header.tsx - owned by Agent B
      Action: commit or stash in wt-frontend before launch

    CONFLICT: Agent C target worktree wt-integration is missing
      Action: spawn the worktree before launch

    WARNING: main worktree has uncommitted changes in:
      docs/README.md - owned by Agent D
      Action: commit or stash before launch

    WARNING: wt-backend branch is 62 commits behind base
      Action: rebase before launch (advisory)

  Agent Overlap:
    OK: Agent A <-> Agent B - no file overlap (parallel, Group 0)
    OK: Agent C depends on Agent A - overlap in src/api.ts is safe

  Result: CONFLICT (2 conflicts, 2 warnings)
```

---

## Command: `plan` - Plan-Specific Validation

### Steps

1. **Read plan** from `[paths].plans/<plan-id>.json` (or `.md`)
2. **Extract file ownership per agent** from the plan:
   - Agent name, file list, dependency edges, group assignment, target worktree
3. **Build overlap matrix**:
   - For each pair of agents, check if any owned files overlap
   - Classify each overlap:

     | Overlap Type | Severity | Resolution |
     |-------------|----------|------------|
     | Same file, agents with dependency | OK | Later agent is authoritative |
     | Same file, parallel agents (same group) | CONFLICT | Split ownership or add dependency |
     | File in `[conflict-zones]`, counterpart in other agent | WARNING | Review co-ownership |

4. **Check against main worktree**:
   ```bash
   git diff --name-only
   git diff --cached --name-only
   ```
   Flag any uncommitted changes that overlap with agent ownership.

5. **Check against active worktrees**:
   Same as `check` command steps 2, 4, 6, and 7 (dirty files, missing target
   worktrees, and stale branches).

6. **Validate conflict zones**:
   - Read `[conflict-zones].zones` from project.toml
   - Each zone is a pair: `"fileA, fileB | reason"`
   - If fileA is owned by Agent X and fileB by Agent Y (different parallel agents),
     flag as WARNING

### Report

```
Worktree Preflight - Plan plan-012

  Agents (4):
    A: api-refactor       - 12 files, Group 0
    B: frontend-update    - 8 files, Group 0
    C: integration        - 5 files, Group 1 (depends: A, B)
    D: docs-update        - 3 files, Group 1 (depends: A)

  Overlap Matrix:
    A <-> B: No overlap (parallel - safe)
    A <-> C: 2 shared files (C depends on A - safe, C authoritative)
    B <-> C: 1 shared file (C depends on B - safe, C authoritative)
    A <-> D: No overlap

  Conflict Zones:
    WARNING: schema.sql (Agent A) <-> DataService.cs (Agent B)
      Reason: schema drift risk
      Suggestion: add dependency edge B->A or assign both to one agent

  Worktree State:
    No active worktrees with conflicts.
    Main worktree: clean

  Result: OK (0 conflicts, 1 warning)
```

---

## Command: `dirty` - Fast Dirty-Worktree Report

Skips all plan analysis. Use for a quick pre-launch sanity check.

### Steps

1. **Inventory active worktrees**:
   ```bash
   git worktree list --porcelain
   ```
2. **Report dirty status** for each worktree using `git -C <path> status --porcelain`.
3. No plan is loaded, no ownership cross-reference, no missing-worktree or
   stale-branch checks. Dirty worktrees are reported as WARNING (no plan
   context to escalate them to CONFLICT).

### Report

```
Worktree Preflight - Dirty

  Active Worktrees:
    wt-frontend  - 3 dirty files (modified)
    wt-backend   - clean
    main         - 1 dirty file (staged)

  Result: WARNING (2 dirty worktrees)
```

---

## Overlap Detection Rules

| Finding | Severity | Resolution |
|---------|----------|------------|
| Same file, agents with dependency | OK | Later agent is authoritative |
| Same file, parallel agents | CONFLICT | Split ownership or add dependency edge |
| Conflict zone, counterpart in other agent | WARNING | Consider co-ownership or dependency |
| Dirty worktree matches agent ownership | CONFLICT | Clean worktree first (commit/stash) |
| Dirty main matches agent ownership | WARNING | Commit or stash before launch |
| Agent target worktree missing | CONFLICT | Spawn the worktree before launch |
| Branch stale > stale-threshold commits behind base | WARNING | Rebase before launch (advisory) |

---

## Integration

| Skill | How Preflight Helps |
|-------|---------------------|
| `$manager run` | Run before launching agents to prevent merge conflicts |
| `$manager go` | Integrate between plan creation and agent launch |
| `$planner` | Validate decomposition before finalizing the plan |
| `$manager run` and `$manager merge` | Adds plan-aware conflict checks before worktree execution and merge operations |
| `$build-gate verify` | Run after preflight to confirm build state before launch |

---

## Conventions

- Read project.toml for all project-specific paths, conflict zones, and the stale-branch threshold
- Never modify plans, specs, or worktrees - only report
- Always provide actionable resolution for every conflict
- Severity vocabulary: OK (safe) / WARNING (review recommended) / CONFLICT (must fix before launch)
- Exit 0 when there are no CONFLICT findings (OK or WARNING only); exit 1 when any CONFLICT is present
