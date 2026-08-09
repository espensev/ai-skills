# AI Skills Repository Rules

## Deep Audit Routing

- Use `deep-audit` for evidence-backed, multi-pass runtime efficiency or
  scalability audits that reconstruct real execution paths across CPU,
  allocation and retention, I/O, concurrency, queues, retries, scheduling, and
  lifecycle behavior.
- Read the canonical Codex contract at
  `codex-skills/skills/deep-audit/SKILL.md`; resolve its references relative to
  that skill directory.
- Deep Audit is read-only toward product code by default. Do not run risky
  profiling, load, fault, restart, privileged, production, or paid activity
  without explicit authority.
- Route ordinary branch or PR review to `review`, one known regression with a
  requested fix to `diagnosing-bugs`, bounded feasibility research to
  `discover`, tests and coverage to `qa`, and security assessment to a
  security-specific workflow. Route parallel audit/remediation, approval gates,
  and implementation ownership to `manager` or another orchestration workflow.

## Package Boundary

- Treat `codex-skills/` and `claude-skills/` as the canonical provider package
  sources. Do not create another full repo-local copy of a skill merely for
  discovery.
- Preserve unrelated dirty-worktree changes and keep package docs, manifests,
  eval cases, tests, and installed-root guidance aligned when changing a skill.
