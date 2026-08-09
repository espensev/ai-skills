---
name: audit-gated-subagents
description: "Review-first Codex workflow for complex audits and gated remediation. Use when the user asks for chief-operator style control, subagents, parallel lanes, audit before fixes, PASS 0 maps, independent plan/spec review, reviewer lanes, or disciplined implementation with explicit gates and no live/system side effects."
---

# Audit-Gated Subagents

Use this skill when a broad request needs disciplined, phase-gated review before
remediation. The controller acts as the chief operator: it gathers context,
assigns bounded sidecar work, verifies every claim, and owns every gate
transition. Subagents can inspect, draft, implement in owned files, and recommend
pass/block outcomes, but they never self-approve a plan, merge, live action, or
final handoff.

This is the heavier sibling of `parallel-agents-light`. Prefer
`parallel-agents-light` for fast two-or-three-lane work. Use this skill when the
work needs a durable PASS 0 inventory, explicit lane packets, independent
reviewers, or strict safety gates. Escalate to `manager` when isolated worktrees,
dependency groups, managed merges, or backend task state are required.

## Controlled Phase Ladder

Run these phases in order. Do not skip ahead because a lane looks easy.

| Phase | Gate | Output |
|---|---|---|
| 0. Authority and safety | Local repo rules, dirty tree, and no-live assumptions are known | Scope note and safety stops |
| 1. PASS 0 inventory | Current structure and risks are mapped read-only | Structural map and findings-first review |
| 2. Lane design | Ownership, dependencies, and validation are explicit | Agent packets and verifier packet |
| 3. Independent plan review | Reviewer returns PASS on the packets | Reviewed plan/spec artifact |
| 4. Implementation | Work stays inside owned files and blocked lanes stop | Focused diffs and lane outputs |
| 5. Independent verification | Controller checks evidence, tests, and residual risk | Gate report and final handoff |

If any gate fails, document the blocker, patch the relevant artifact, and repeat
that phase. Do not treat a blocked gate as approval to proceed.

## Core Rules

1. Load local authority first.
   - Read repo instructions, safety notes, build/test docs, active plans, and
     current status docs before planning.
   - Check `git status --short --branch`; check worktrees or active task state
     when the repo uses them.
   - Treat unrelated dirty or untracked paths as user or agent work unless
     proven otherwise.

2. Start read-only.
   - Do not implement fixes during inventory.
   - Do not run live services, hardware, scheduled tasks, destructive cleanup,
     deploys, account changes, or external mutations unless the user explicitly
     asked for that live operation.
   - If the user says review-only, stop after review artifacts and plan/spec
     review.

3. Run PASS 0 inventory.
   - Build a structural map of files, modules, entry points, public surfaces,
     imports, consumers, and generated/vendor exclusions.
   - Flag complexity hotspots: fan-out modules that import many sources, fan-in
     modules that many consumers depend on, large files, and shared startup or
     package surfaces.
   - Scan for stale-generation markers: TODO, FIXME, HACK, stale comments,
     docs/source conflicts, duplicated logic, and mid-file style drift.
   - Treat git history and blame concentration as risk signals, not proof of
     authorship.

4. Save durable review artifacts.
   - Put reviews, structural maps, lane specs, and gate reports in the repo's
     review/status surface.
   - Findings lead; summaries follow.
   - Every material claim needs a file path, line number, command output, or
     artifact reference.

5. Create lanes only after PASS 0.
   - Split by file ownership and dependency order.
   - Each editing lane gets objective, required reads, owned files, read-only
     evidence, out-of-scope list, safety stops, validation, and output artifact.
   - Include reviewer lanes. No lane reviews or approves itself.
   - Prefer fewer lanes unless ownership is clean.

6. Require independent plan/spec review.
   - A reviewer lane audits the plan/spec packet before implementation.
   - If the reviewer returns FAIL, patch the specs and repeat review.
   - Do not start remediation until this gate passes and the user has not scoped
     the task to review-only.

7. Implement only after the gate.
   - Keep edits inside owned files.
   - Stop a lane if active dirty work overlaps its owned files.
   - Keep live, production, deploy, credential, and operator-owned decisions in
     the controller thread.

8. Verify after implementation.
   - Each implementation lane gets independent review before acceptance.
   - The controller verifies diffs, artifacts, tests, reviewer findings, and
     remaining risk.
   - Close with facts: what changed, what was validated, what remains deferred,
     and which gates passed.

## Chief Operator Gate

Use this gate for high-risk flows:

- Subagents may collect evidence, run read-only checks, draft patches in owned
  files, and recommend pass/block.
- The controller/operator alone may authorize gate transitions, final pass
  markers, live actions, deployment, destructive cleanup, or merge/ship
  readiness.
- A gate cannot pass from a verbal assertion alone. It needs artifacts or command
  evidence that the controller has checked.
- A blocked gate becomes a documented blocker with exact missing proof, not an
  implicit approval to continue.

When a CC Workflow Studio run observer is in use, emit JSONL events matching the
existing run-observer contract for node `start`, `finish`, `branch`, `error`,
and `note` transitions.

## PASS 0 Output

Minimum artifacts:

- Structural map: file/module inventory plus fan-in/fan-out and shared-surface
  flags.
- Pre-audit review: findings-first, with safety and dirty-tree notes.
- Remediation plan: goal, exit criteria, roster, dependency graph, ownership,
  conflict zones, risks, verification, and docs updates.
- Agent packets: one file per lane plus reviewer/verifier packets.
- Independent plan review: PASS/FAIL before implementation.

For the detailed checklist and packet templates, read
`references/pass0-and-gates.md` when running a full campaign.

## Lane Design Rules

- Own paths, not themes. Every editing lane must list exact files or a narrowly
  bounded path.
- Keep current-state docs and historical records separate.
- Use source-level fixes only for concrete issues.
- Comment-only lanes must stay comment-only.
- Treat generated-output cleanup as a repo-hygiene lane, not a broad clean
  command.
- Put reviewer outputs under the repo's review artifact surface.
- If a reviewer finds a spec gap, patch the spec before implementation.

## Safety Stops

Stop and report instead of proceeding when:

- another user or agent is editing the same owned files;
- the task would arm writes, modify services/tasks, run live hardware, deploy, or
  change external state without explicit live-operation approval;
- the plan lacks file ownership or validation;
- an independent reviewer returns FAIL;
- a command fails because the documented repo workflow is broken.

## Validation Ladder

- Review-only: readback plus `git diff --check` when artifacts changed.
- Docs-only: readback, link/path check, `git diff --check`.
- Source comment-only: readback changed block, `git diff --check`; build only
  when behavior changed.
- Source behavior: repo-native build/test wrapper.
- Release/script/deploy lanes: repo-native release or CI wrapper, not ad hoc
  replacement unless debugging that wrapper.
