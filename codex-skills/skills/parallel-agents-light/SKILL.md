---
name: parallel-agents-light
description: "Lightweight Codex orchestration for Claude-style parallel subagents, Ultracode-light workflows, bounded sidecar agents, and fast split-review or split-implementation passes. Use when the user asks Codex to use parallel agents, subagents, swarm-style work, lightweight multi-agent coding, independent reviewers, or faster split execution without committing to a full manager campaign."
---

# Parallel Agents Light

Use this skill to get useful parallelism without paying the coordination cost of
a full campaign. The controller stays responsible for repo state, integration,
verification, and the final answer.

## Decision Ladder

Choose the lightest mode that can finish the task safely:

1. **Local loop**: use the main Codex thread when the work is one objective in
   one tight file set. Pull in `$loop` if repeated inspect/edit/verify cycles
   are enough.
2. **Read-only sidecars**: launch 1-3 bounded subagents for independent
   evidence gathering, review, docs drift checks, test mapping, or risk scans.
   Keep all writes with the controller.
3. **Split implementation**: launch 2-3 workers only when each worker has a
   disjoint write set and a clear verification command. Keep one integration
   owner in the controller thread.
4. **Full campaign**: escalate to `$manager` when the work needs durable plan
   artifacts, worktrees, dependency groups, managed merges, or more than three
   write lanes.
5. **External orchestration**: use `$dmux-workflows` when the user explicitly
   wants dmux, tmux, panes, or terminal-session orchestration.

## Preflight

Before launching workers:

- Inspect current repo state with `git status --short` when a git repo exists.
- Read the files needed to define ownership. Do not launch blind workers from a
  vague prompt.
- State or internally record the roster: objective, owned files or read-only
  concern, expected output, and verification.
- Prefer 2 workers by default. Use 3-4 only when the file boundaries are clean.
- Avoid parallel writes to package manifests, startup entrypoints, shared
  schemas, generated files, and global config unless one worker owns the file
  and the others are read-only.

## Worker Types

Use sidecars for:

- independent code review of a diff or narrow file set
- docs/code drift checks
- test selection and failure triage
- search and evidence collection across separate modules
- mechanical but bounded edits in owned files

Keep the controller on:

- architecture decisions
- final merge and conflict resolution
- release/deploy approval
- destructive cleanup
- secrets, credentials, or raw sensitive data
- live hardware, production, or operator-owned actions

## Model Tiering

When the subagent launcher exposes model tiers, route intentionally:

- **mini / Spark-class**: read-only review, docs drift, test mapping, simple
  extraction, straightforward rewrite, small mechanical edits.
- **standard**: normal implementation in a bounded file set, test fixes, local
  integration.
- **max**: ambiguous architecture, difficult debugging, cross-cutting refactors,
  security-sensitive reasoning that must stay with the controller or a strong
  reviewer.

Prefer a Spark-class Codex subagent for cheap bounded sidecars when available.
If the tier is unavailable, use the closest available stronger tier rather than
blocking the workflow.

## Launch Contract

When an Agent or subagent tool is available, launch all initially ready workers
in one tool message so they actually run in parallel. If no subagent tool is
available, fall back to sequential sidecar-style passes and say that live
parallel launch was unavailable.

Each worker prompt should include:

- the task objective in one sentence
- owned files, or an explicit read-only scope
- what not to touch
- source files or commands already inspected by the controller
- expected verification command or evidence standard
- an output contract with changed files, findings, tests run, blockers, and
  residual risk

Use this compact prompt shape:

```text
You are Worker <letter> for a Codex light-parallel pass.
Objective: <one concrete outcome>.
Scope: <owned files or read-only concern>.
Do not touch: <shared files, unrelated areas, destructive actions>.
Context already gathered: <paths, commands, relevant facts>.
Verification: <command or evidence expected>.
Return: summary, changed files, verification, blockers, residual risk.
```

## Integration

After workers finish:

1. Read each result before editing.
2. Compare claims against files, diffs, or command output.
3. Apply or merge only the useful changes into the controller worktree.
4. Run the narrowest meaningful verification, then broader checks if shared
   behavior changed.
5. Use `$review` or a fresh read-only sidecar for independent final review when
   the user requested verification by another agent.

Never treat a sidecar result as authoritative without controller verification.
Report worker disagreement as a finding, not as a hidden decision.

## When To Escalate

Stop using this light skill and use `$manager` when any of these are true:

- workers need isolated worktrees or branch ownership
- several workers must write to related code paths
- merge order or dependency groups matter
- the task needs durable campaign docs, agent specs, or tracker updates
- a worker failure blocks downstream work
- the user asks for a managed multi-agent campaign instead of a fast split pass

Use `$delegate` instead of subagents only for narrow local-model transforms on
material the controller already fetched. Local delegation does not replace
subagent review, implementation, or planning.
