---
name: worktree-manager
description: Create, list, merge, and teardown git worktrees for parallel AI agent development. Handles port allocation, scope assignment, dependency bootstrap, and smallest-diff-first merge coordination.
argument-hint: "<command> [args] — spawn | list | merge | teardown | scope | ports | diff"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write, Agent
user-invocable: true
---

# Worktree Manager — Parallel Agent Orchestration

You manage git worktrees for parallel AI agent development. You create isolated
worktrees with deterministic port allocation and file scope assignment, coordinate
merges in smallest-diff-first order, and safely tear down completed work.

**All commands run to completion autonomously except `merge`, which confirms
with the user when conflicts are predicted.**

**Runtime:** `wt` CLI from `ai-skills/wt-cli/` (TypeScript/Node.js)
**Config:** `.claude/skills/project.toml` — project-specific paths, commands, modules

## Commands

| Command | Usage | Purpose |
|---------|-------|---------|
| `spawn` | `/worktree-manager spawn <name> [--scope <path>]` | Create worktree + branch + bootstrap |
| `list` | `/worktree-manager` or `/worktree-manager list` | Show all worktrees with status |
| `merge` | `/worktree-manager merge <name>` or `merge --all` | Merge branches, smallest-diff-first |
| `teardown` | `/worktree-manager teardown <name>` or `teardown --all` | Safe removal with checks |
| `scope` | `/worktree-manager scope <name> <path>` | Assign file scope to a worktree |
| `ports` | `/worktree-manager ports` | Show port allocation table |
| `diff` | `/worktree-manager diff <name>` | Show diff stats against merge base |

Default to `list` if no command given.

---

## Setup: Verify Runtime

Before any command, verify the `wt` CLI is available:

1. Check if `wt` is on PATH:
   ```bash
   wt --version
   ```

2. If not found, check for the local install:
   ```bash
   node ai-skills/wt-cli/dist/cli.js --version
   ```

3. If neither works, install it:
   ```bash
   cd ai-skills/wt-cli && npm install && npx tsup && cd -
   ```

Use whichever invocation works (`wt` or `node <path>/dist/cli.js`) for all
subsequent commands.

---

## Command: `spawn` — Create Worktree

Create a new worktree with branch, bootstrap, and metadata.

### Usage:

- `/worktree-manager spawn auth` — basic spawn
- `/worktree-manager spawn auth --scope src/auth` — with file scope
- `/worktree-manager spawn payments --port 3100` — explicit port
- `/worktree-manager spawn api --skip-install` — skip dependency install

### Steps:

1. **Validate the repo** is a git repository:
   ```bash
   git rev-parse --show-toplevel
   ```

2. **Check existing worktrees** to avoid conflicts:
   ```bash
   wt list --json
   ```

3. **Spawn the worktree:**
   ```bash
   wt spawn <name> --scope <path>
   ```

   The CLI handles:
   - Creating `../wt-<repo>-<slug>/` sibling directory
   - Creating `agent/<slug>` branch from HEAD
   - Allocating a deterministic port (3000-3999 range)
   - Installing dependencies (pnpm > yarn > npm, uv > pip)
   - Copying `.env.example` to `.env`
   - Writing `.worktree/local.json` metadata
   - Enabling `extensions.worktreeConfig` for per-worktree git config

4. **Report** the created worktree's path, branch, port, and scope.

### Rules:

- Start with 2-3 active agent worktrees unless scopes are clearly disjoint
- Always assign a scope before starting work in the worktree
- Reserve shared hotspots (lockfiles, root manifests, route registries, barrel
  exports, migrations, schema snapshots, generated clients) for one owner only

---

## Command: `list` — Show Worktrees

Display all worktrees with their status.

### Steps:

1. **List worktrees:**
   ```bash
   wt list --all
   ```

2. **Report** the table showing name, branch, port, scope, lock status, and
   dirty/clean state for each worktree.

For JSON output (useful for programmatic checks):
```bash
wt list --all --json
```

---

## Command: `merge` — Coordinated Merge

Merge worktree branches into the target branch using smallest-diff-first ordering.

### Usage:

- `/worktree-manager merge auth` — merge one worktree
- `/worktree-manager merge --all` — merge all worktree branches
- `/worktree-manager merge --all --dry-run` — preview merge order

### Steps:

1. **Preview the merge plan:**
   ```bash
   wt merge --all --dry-run
   ```
   This shows each branch's diff size, ordering, and conflict predictions.

2. **If conflicts are predicted**, ask the user whether to proceed or skip
   the conflicting branches.

3. **Execute merges** in smallest-diff-first order:
   ```bash
   wt merge <name> --delete-branch
   ```
   Or for all:
   ```bash
   wt merge --all --delete-branch
   ```

4. **After all merges**, verify the result:
   ```bash
   git log --oneline -10
   git status --short
   ```

### Merge policy:

- Always merge sequentially, smallest diff first
- Skip branches with predicted conflicts — report them for manual resolution
- Use `--no-ff` merges to preserve branch history
- Delete source branches after successful merge (`--delete-branch`)

---

## Command: `teardown` — Safe Removal

Remove worktrees with safety checks.

### Usage:

- `/worktree-manager teardown auth` — remove one worktree
- `/worktree-manager teardown auth --delete-branch` — also delete the branch
- `/worktree-manager teardown --all` — remove all non-primary worktrees

### Steps:

1. **Check for uncommitted changes:**
   ```bash
   wt diff <name>
   ```

2. **If uncommitted changes exist**, warn the user and ask for confirmation.
   Do not use `--force` without explicit approval.

3. **Remove the worktree:**
   ```bash
   wt teardown <name> --delete-branch
   ```

4. **Verify removal:**
   ```bash
   wt list --all
   ```

### Safety rules:

- Never remove the primary worktree
- Never use `--force` without user confirmation
- Always show uncommitted changes before removing
- Always prune worktree metadata after removal

---

## Command: `scope` — Assign File Scope

Set or update the file/directory scope for a worktree.

### Steps:

1. **Set the scope:**
   ```bash
   wt scope <name> <path>
   ```

2. **Verify:**
   ```bash
   wt list --all
   ```

### Scope rules:

- Every worktree should have a scope assigned before work begins
- Scopes should not overlap between concurrent worktrees
- Use directory paths for broad scope (`src/auth/`)
- Use file patterns for narrow scope (`src/auth/middleware.ts`)

---

## Command: `ports` — Port Allocation Table

Show which ports are allocated to which worktrees.

```bash
wt ports
```

Ports are allocated deterministically from the 3000-3999 range using a SHA256
hash of the worktree path. This ensures the same worktree always gets the same
port, avoiding conflicts between concurrent dev servers.

---

## Command: `diff` — Diff Stats

Show diff statistics for a worktree branch against the merge base.

```bash
wt diff <name>
```

Shows per-file changes, total insertions, deletions, and files changed. Useful
for assessing merge complexity before coordinating merges.

For JSON output:
```bash
wt diff <name> --json
```

---

## Workflow: Multi-Agent Campaign

The typical workflow for a multi-agent campaign:

1. **Plan**: Identify 2-3 independent task scopes
2. **Spawn**: Create worktrees with non-overlapping scopes
   ```bash
   wt spawn auth --scope src/auth
   wt spawn payments --scope src/payments
   wt spawn notifications --scope src/notifications
   ```
3. **Work**: Each agent works in its own worktree
4. **Review**: Check diff sizes and conflict potential
   ```bash
   wt merge --all --dry-run
   ```
5. **Merge**: Merge smallest-diff-first
   ```bash
   wt merge --all --delete-branch
   ```
6. **Cleanup**: Remove remaining worktrees
   ```bash
   wt teardown --all
   ```

---

## Conventions

- Worktree paths follow the `../wt-<repo>-<slug>` sibling convention
- Branch names follow the `agent/<slug>` convention
- Metadata lives in `.worktree/local.json` (excluded from git via `.git/info/exclude`)
- Port range: 3000-3999 (deterministic, SHA256-based)
- Prefer pnpm for JavaScript projects (80% disk savings with hardlinks)
- On Windows: enable `core.longpaths`, keep worktree names short
- Read the conventions file (`[project].conventions` in project.toml) for project style
