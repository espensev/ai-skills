---
name: worktree-preflight
description: "Validate planned agent file ownership against dirty worktrees, missing worktrees, stale branches, uncommitted changes, and parallel-agent overlaps. Use before launching a multi-agent campaign or assigning parallel work."
---

# Worktree Preflight Protocol

## Core Mandate
Before launching parallel agents into worktrees, verify that the plan's file ownership matches the current worktree state, that every agent's target worktree exists, that branches are not dangerously stale, and that no uncommitted changes will collide. Catch coordination failures before they corrupt agent output.

## Execution Rules
1. **Read-only:** Worktree-preflight is a verification skill. Never modify worktrees, branches, plans, or uncommitted state — only report.
2. **Evidence over intuition:** Every finding must cite the agent name, the contested file or worktree, and the actual git worktree status.
3. **Block before launch:** If preflight reports any CONFLICT, the manager must NOT proceed to `/manager run` without explicit user override.
4. Follow the global guardrails in AGENTS.md.

## Config
Read `project.toml`:
- `[paths].plans` — plan file directory (JSON plans at `[paths].plans/*.json`, or markdown plans with agent tables)
- `[conflict-zones]` — known high-risk file pairs, each `"fileA, fileB | reason"`
- `[worktree-preflight].stale-threshold` — commits-behind-base limit for the stale-branch check (default: 50)

## Commands
- `/worktree-preflight` or `/worktree-preflight check` — full preflight against the latest `executing`/`approved` plan (default)
- `/worktree-preflight plan <id>` — preflight a specific plan ID
- `/worktree-preflight dirty` — fast path: report only dirty worktrees, no plan analysis

## What `check` / `plan` Verify
1. **Worktree inventory** — `git worktree list --porcelain` enumerates active worktrees (path, branch, HEAD).
2. **Dirty worktrees** — for each worktree, run `git -C <path> status --porcelain` (and `git -C <path> diff --name-only` / `--cached` / `HEAD`); collect modified, staged, and untracked files.
3. **Plan file ownership** — read the active plan and extract each agent's owned file list, dependency edges, group, and target worktree.
4. **Ownership overlap** — for parallel agents (same dependency group), flag any file claimed by two or more agents. Overlap between sequential agents (dependency edge) is safe — the later agent is authoritative.
5. **Dirty + claimed collision** — flag any file that is both uncommitted in a worktree AND claimed by a future agent.
6. **Missing worktree** — flag any agent whose declared target worktree is absent from the inventory.
7. **Stale branches** — using `git -C <path> rev-list --count HEAD..<base>`, flag any worktree branch more than the stale-threshold commits behind base (advisory).
8. **Conflict zones** — if the two files of a `[conflict-zones]` pair are owned by different parallel agents, flag for review.

`dirty` performs only steps 1–2 (no plan load, no overlap/missing/stale checks).

## Severity
| Finding | Severity | Action |
|---------|----------|--------|
| Same file, agents with dependency edge | OK | Later agent is authoritative — no action |
| Same file, parallel agents (same group) | CONFLICT | Split ownership or add a dependency edge |
| Dirty worktree file claimed by an agent | CONFLICT | Commit, stash, or clean the worktree before launch |
| Uncommitted file also claimed by next agent | CONFLICT | Resolve the uncommitted change first |
| Agent target worktree missing | CONFLICT | Spawn the worktree before launch |
| Dirty main matches agent ownership | WARNING | Commit or stash before launch |
| Conflict-zone pair split across parallel agents | WARNING | Consider co-ownership or a dependency edge |
| Branch stale > stale-threshold commits behind base | WARNING | Rebase before launch (advisory) |
| Dirty worktree under `dirty` command (no plan context) | WARNING | Review before launch |

## Output Contract
Emit a structured report:
- **Active Worktrees**: name, branch, dirty file count, commits-behind-base
- **Pending Plan / Agents**: agent → owned files, group, dependencies, with overlaps flagged
- **Conflicts**: ordered list of CONFLICT and WARNING items, each with the offending agent/file and an explicit recovery action
- **Result** line: `OK`, `WARNING`, or `CONFLICT` with conflict/warning counts

Severity vocabulary: OK (safe) / WARNING (review recommended) / CONFLICT (must fix before launch).

Exit 0 when there are no CONFLICT findings (OK or WARNING only). Exit 1 when any CONFLICT is present.
