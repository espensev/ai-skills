## Local Package Guidance

- Treat this folder as the source package for an experimental Gemini adapter.
- Keep the package docs concise and explicit about what exists today versus
  what is still planned.
- Default to editing package-root files in this folder rather than copying
  files from `claude-skills` or `codex-skills`.

## Repo Conventions

- This package is docs-first by design.
- Do not introduce a Gemini-specific clone of `scripts/`, `tests/`, or
  `planning-contract.md` until the shared runtime is extracted into a neutral
  core.
- When discussing the consumer repo layout, use Gemini paths such as
  `GEMINI.md` and `.gemini/commands/`.
- When discussing this package repo, refer to package-root files in
  `gemini-skills/`.
- Prefer command wrappers and instruction files over provider-specific backend
  forks.

## Portability Guardrails

- Avoid hard-coded references to `.claude/skills`, `.codex/skills`, or
  provider-specific worktree paths in Gemini-facing examples.
- Keep the generic skill names stable when describing the shared campaign
  surface: `discover`, `planner`, `brief`, `manager`, `ship`, `qa`, `loop`,
  `loop-master`.
- Ensure specialized Gemini commands are documented: `epic-refactor`,
  `forensic-debugger`, `ui-test-engineer`, `doc-weaver`.
- If a future Gemini runtime needs extra metadata, document the provider delta
  first and only then add files.
- Reuse the existing lightweight eval model before inventing a Gemini-only
  scoring system.

## Global Multi-Agent Guardrails

1. Contract-first execution: if a command depends on an upstream artifact
   such as `docs/system-map.md`, `docs/planning-contract.md`, or a
   task-specific `docs/briefs/task-<id>.md`, read it first. If it is missing,
   stale, or malformed, halt and report the blocker. Implementation agents
   must never start a task without a corresponding context brief.
2. Strict write scope: only write the artifact files owned by the active
   command plus the source files explicitly in scope for that command. No
   opportunistic cleanup, drive-by refactors, or speculative edits.
3. Evidence before conclusions: every material claim about code, logs, tests,
   or documentation must be backed by source evidence such as `file:line`,
   command output, timestamps, or attached artifacts. Mark anything else as a
   hypothesis.
4. Verification before sign-off: do not claim a fix, sync, or migration is
   complete without naming the validation command or explaining the exact
   reason validation could not be run.
5. Sensitive-data handling: do not copy raw secrets, tokens, personal data, or
   customer content from logs, screenshots, or traces into generated artifacts.
   Redact or summarize sensitive values.
6. Stay in lane: discovery documents what exists, planners design the work,
   documentation sync edits docs, and code-changing commands edit only the code
   they own. Crossing roles requires an explicit user request or contract.
7. The Lens Strategy (Read-All, Write-Scoped): When operating as Gemini, leverage the large context window to ingest maximum repository context for perfect comprehension, but strictly limit write operations to the active task boundaries defined by the Planning Contract. Do not use the massive context window to make unauthorized, cross-cutting "drive-by" edits.
8. Feedback before memory: treat explicit user corrections, failing verification
   commands, repeated QA findings, and scored eval misses as the highest-signal
   feedback. Do not promote a one-off symptom into a reusable instinct, rule,
   or agent behavior unless it repeats or the user explicitly asks to codify it.
