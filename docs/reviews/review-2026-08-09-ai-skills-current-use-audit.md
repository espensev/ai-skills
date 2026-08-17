# AI-Skills Current-Use Audit

**Date:** 2026-08-09
**Status:** complete
**Scope:** `D:\Development\AI-related\Ai-Skills` source, package contracts,
release tooling, ignored residue, and read-only comparison with current local
Codex, Claude, shared-agent, and retired provider surfaces.

## Current-use baseline

- The controller identity was verified as `snd-desk` before repository
  mutations.
- Codex and Claude are the active local provider surfaces. Their user roots are
  junctions into `D:\DevHome\state\codex` and `D:\DevHome\state\claude`.
- Shared skills under `D:\DevHome\state\agents` remain a separate ownership
  plane and were not folded into either provider package.
- No local Gemini CLI or installed Gemini skill projection exists. After the
  initial conservative retention decision, the user confirmed there is no
  remaining relevant consumer; the adapter was removed coherently.
- No Antigravity command, installed root, or release consumer exists. Existing
  package deletions were therefore completed coherently across manifests,
  readiness docs, and scripts.
- Installed/live roots are projections, not source authority. This audit did
  not overwrite them.

## Decisions applied

### Retired

- Removed Antigravity from the release surface and deleted its dead validation,
  export, count, and parity branches.
- Removed the legacy Gemini package and its validation, export, count, parity,
  sync-template, package-specific ignore, and current documentation branches
  after explicit user confirmation that it is no longer relevant.
- Removed the Claude-only `observer-test`, `refactor-planner`, and
  `worktree-manager` source aliases. Current behavior is owned by `observer`,
  `planner --mode refactor`, and `manager` plus its task runtime and hooks.
- Removed `dmux-workflows`. Both Codex projections disabled it, observed command
  history had no invocation, no `dmux` executable was present, and its guidance
  depended on an unavailable model tier. `parallel-agents-light` now gives a
  tool-available terminal-orchestration fallback directly.
- Removed `wt-cli`. Its only documented consumer was the retired
  `worktree-manager`; current managers use the Python task runtime, no npm
  installation existed, and `wt.exe` resolves to Windows Terminal.

### Added or promoted

- Added `skill-authoring` to both ready packages.
- Added the evaluated Claude `deep-audit` package and its support references.
- Added Codex eval coverage for `audit-gated-subagents` and `skill-authoring`,
  and Claude coverage for `deep-audit` and `skill-authoring`.
- Kept `codebase-review-prompts` source-only because the shared agent catalog
  owns the active local copy. Kept `telemetry-live-ops` source-only because it
  is machine-local.
- Kept `loop-master` as an explicit backward-compatibility alias.

### Hardened

- Made strict manifest equality part of release readiness.
- Added skill folder/frontmatter-name equality, kebab-case, and support-file
  reference checks to package validation.
- Prevented `__pycache__`, `.pyc`, and `.pyo` artifacts from entering exports,
  installs, or live-root comparisons.
- Canonicalized junction identities so profile aliases and state roots are not
  processed twice.
- Added LF repository attributes and anchored the ignored donor path as
  `/Deep-Audit/`, leaving the real `skills/deep-audit` payloads visible to Git.

## Cleanup

- Removed the tracked/reproducible `wt-cli` source and its ignored dependency
  and build outputs.
- Removed the 115-file legacy Gemini adapter (515,808 bytes); its tracked source
  remains recoverable from Git history.
- Removed 4,324 ignored cache, test-temp, bytecode, old export, and zero-byte
  files (49.42 MiB).
- Removed the ignored March Codex campaign snapshot after confirming it still
  claimed running/blocked agents while no campaign worktrees existed.
- Total measured space reclaimed by the package and ignored-residue cleanup was
  about 104.5 MiB.

The dirty nested `cc-workflow/cc-wf-studio` and top-level `skills` repositories
were preserved, including their ignored dependencies, because they contain
unrelated current work. `.tmp/deep-audit-eval`, the Deep-Audit donor kit, and
the pinned `claude-memory-manager` provenance clone were also preserved.

## Validation

- `Test-ReadyPackages.ps1 -StrictSkillManifest`: pass, 36 Codex + 23 Claude.
- `Test-ReleaseReadiness.ps1`: pass, including strict packaging, README counts,
  contract tests, provider parity, and diff whitespace checks.
- Codex full pytest suite: 694 passed.
- Claude full pytest suite: 766 passed.
- Focused skill-doc tests: Codex 12 passed; Claude 10 passed.
- Deterministic light evals: Codex 39/39; Claude 22/22; both average 5/5.

## Deferred and delivery notes

- Live provider roots remain intentionally unsynced. They contain stale and
  locally divergent files, so a blanket forced install would be unsafe. In
  particular, the shared catalog already owns `skill-authoring`, while the live
  Codex copy of `parallel-agents-light` still routes to retired `dmux-workflows`.
- Six new manifest-referenced payloads form one atomic delivery unit with their
  manifest changes: Codex `audit-gated-subagents`,
  `codebase-review-prompts`, `deep-audit`, and `skill-authoring`; Claude
  `deep-audit` and `skill-authoring`.
- Two references outside this repository still use the obsolete
  `D:\Development\Ai-Skills` path:
  `D:\DevHome\shell\tests\Test-CodexMemory.ps1` and
  `C:\Users\Sev\.claude\CLAUDE.md`. They were not changed because this audit
  was scoped to the AI-Skills repository.
- A pre-existing task-runtime cache fingerprint can miss a changed non-maximum
  spec mtime. One parallel run exposed the flake; isolated and sequential full
  suites passed. Fixing it should use the diagnosing-bugs workflow rather than
  being folded into this cleanup.
- At audit time, the repository had 36 stashes, including six exact duplicate
  snapshots, and a local branch with two unique commits. Neither was pruned
  during the audit.
