# AI Skills Repository Rules

## Deep Audit Routing

- Use `/deep-audit discover <scope>` for a new evidence-backed, multi-pass
  runtime efficiency or scalability audit. Other supported modes are `trace`,
  `audit`, `deepen`, `verify`, `profile`, `resume`, and `report`.
- Read the canonical Claude contract at
  `claude-skills/skills/deep-audit/SKILL.md`; resolve its references relative to
  that skill directory.
- Deep Audit is read-only toward product code by default. Do not run risky
  profiling, load, fault, restart, privileged, production, or paid activity
  without explicit authority.
- Route ordinary branch or PR review to `/review`, one known regression with a
  requested fix to `/diagnosing-bugs`, bounded feasibility research to
  `/discover`, tests and coverage to `/qa`, and security assessment to a
  security-specific workflow. Route parallel audit/remediation, approval gates,
  and implementation ownership to `/manager` or `Workflow`.

## Package Boundary

- Treat `claude-skills/` and `codex-skills/` as the canonical provider package
  sources. Do not create another full repo-local copy of a skill merely for
  discovery.
- Treat `codex-skills/local-hooks/devhome-lifecycle/` as the machine-local
  source for Codex lifecycle hooks and the shared Claude/Codex Handoff Relay.
  Keep it outside the portable release and provider install manifests. Its
  plugin cache, DevHome runtime projections, enablement, and hook trust are
  separate operational state; use the source installers rather than editing or
  exporting installed copies.
- Treat `scripts/AiEnvironment/` as the read-only wanted-state observer for
  the effective Codex and Claude environment. `profiles/` is reviewed intent,
  `locks/` is the commit-backed promotion artifact, and
  `D:\DevHome\state\ai-environment\*.observed.json` is generated output; never
  hand-edit the report, never mark a lock `accepted` from a dirty worktree, and
  do not add apply or repair paths that bypass an accepted lock.
- This repository remains read-only for Claude unless the user explicitly
  authorizes a package change.
