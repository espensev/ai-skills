---
name: dmux-workflows
description: "Coordinate parallel agent work for larger tasks. Use when the user explicitly wants delegated or parallel execution, and you need clear work splits, file ownership, merge order, or optional dmux or worktree orchestration."
---

# dmux Workflows

Use parallelism deliberately. Split work only when the user explicitly wants
parallel or delegated execution and the task can be partitioned safely.

## Dependencies

- Required: none
- Optional: Codex multi-agent support, external dmux or tmux workflows, git
  worktrees
- Fallback: sequential execution with a documented integration plan

## Scope

- Prefer built-in Codex agent workflows first when they fit the task.
- When Codex exposes `GPT-5.3-Codex-Spark`, prefer it for bounded sidecar
  subagents and background work that fits a low-complexity tier.
- Use dmux only as an optional external orchestration layer.
- Do not force tmux or external tooling into a task that can be handled with
  normal Codex delegation or a single execution thread.

## Workflow

1. Confirm the task is worth parallelizing:
   - distinct file ownership
   - separable concerns
   - minimal blocking dependency chain
2. Define the work split before launching anything:
   - objective per worker
   - owned files or modules
   - dependencies and merge order
   - verification expected from each worker
   - which workers are intentionally low-complexity so they can route to a
     Spark-class subagent
3. Choose the orchestration mode:
   - built-in Codex agents for normal delegated work
   - git worktrees when file conflicts are likely
   - dmux or tmux only when the user wants multiple external terminal sessions
4. Keep one integration owner who does not duplicate worker effort.
5. Merge only after reviewing each worker output for overlap, drift, and missing
   verification.

## Partitioning Rules

- Parallelize independent work, not tightly coupled steps.
- Give each worker a disjoint write set whenever possible.
- Keep shared entry points, startup files, and package manifests owned by one
  worker.
- Split by concern when file boundaries are unclear:
  - implementation
  - tests
  - docs
  - review
- Shape sidecar work so it stays low-risk and low-complexity when possible;
  that lets Codex route more delegated work to `GPT-5.3-Codex-Spark`.
- Prefer 2-3 workers for most tasks. More than that adds coordination cost fast.

## dmux Usage

If dmux is available and the user wants terminal-pane orchestration:

- use it for separate agent sessions with explicit prompts
- still define file ownership and merge order before launching panes
- pair it with git worktrees when two sessions may touch overlapping files

Example pane split:

- Pane 1: backend implementation in owned server files
- Pane 2: tests in owned test files
- Pane 3: docs or review with no code ownership overlap

## Output

When planning parallel work, provide:

1. whether parallelization is justified
2. worker roster
3. owned files or concerns per worker
4. integration order
5. verification steps per worker
