## Local Package Guidance

- Treat this folder as the source package for the Antigravity adapter.
- Keep package docs explicit about what ships today versus what remains legacy
  Gemini or ECC reference material.
- Default to editing package-root files in this folder. Do not copy large
  trees from `gemini-skills`, `claude-skills`, `codex-skills`, or the ignored
  ECC mirror unless a manifest-listed promotion requires it.

## Repo Conventions

- This package is docs-first by design.
- Do not introduce an Antigravity-specific clone of the Claude/Codex Python
  runtime. Shared runtime work belongs in a neutral core.
- When discussing the installed consumer layout, use Antigravity paths:
  `AGENTS.md`, `.agents/skills/`, and `.agent/workflows/`.
- When discussing this package repo, refer to package-root files in
  `antigravity-skills/`.
- Prefer Agent Skills and workflow files over provider-specific backend forks.

## Portability Guardrails

- Avoid hard-coded references to `.claude/skills`, `.codex/skills`, or
  `.gemini/skills` in Antigravity-facing examples.
- Keep generic skill names stable when describing the shared campaign surface:
  `discover`, `planner`, `brief`, `manager`, `ship`, `qa`, `loop`,
  `loop-master`.
- If Antigravity adds or changes provider metadata, document the provider delta
  first and only then add files.

## Global Multi-Agent Guardrails

1. Contract-first execution: if a workflow depends on an upstream artifact such
   as `docs/system-map.md`, `docs/planning-contract.md`, or a task-specific
   `docs/briefs/task-<id>.md`, read it first. If it is missing, stale, or
   malformed, halt and report the blocker.
2. Strict write scope: only write artifact files owned by the active workflow
   plus source files explicitly in scope for that workflow. No opportunistic
   cleanup, drive-by refactors, or speculative edits.
3. Evidence before conclusions: every material claim about code, logs, tests,
   or documentation must be backed by source evidence such as `file:line`,
   command output, timestamps, or attached artifacts. Mark anything else as a
   hypothesis.
4. Verification before sign-off: do not claim a fix, sync, or migration is
   complete without naming the validation command or explaining why validation
   could not be run.
5. Sensitive-data handling: do not copy raw secrets, tokens, personal data, or
   customer content from logs, screenshots, or traces into generated artifacts.
   Redact or summarize sensitive values.
6. Stay in lane: discovery documents what exists, planners design the work,
   documentation sync edits docs, and code-changing workflows edit only the
   files they own. Crossing roles requires an explicit user request or contract.
7. Read-all, write-scoped: use Antigravity's large workspace context for
   comprehension, but keep writes inside the active task boundaries.
8. Feedback before memory: treat explicit user corrections, failing
   verification commands, repeated QA findings, and scored eval misses as the
   highest-signal feedback. Do not promote a one-off symptom into reusable
   behavior unless it repeats or the user explicitly asks to codify it.
