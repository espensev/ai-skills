# Discovery — Claude Workflow Durability

**Goal:** Get the current Claude/AI-Skills status and identify how to make the
review-controller and Handoff Relay workflow reproducible and durable.
**Date:** 2026-08-30
**Status:** complete
**Recommended next:** Ready to plan the package/acceptance changes; do not
promote the current environment lock first.

## Questions

1. What is the live repository state and dirty-work scope?
2. Which source, package, projection, and runtime surfaces govern the Claude workflow?
3. What validation evidence is current, and what is still unverified?
4. Where can the workflow lose durability through drift or missing gates?
5. What is the smallest repeatable durability gate?

## Findings

### Q1: What is the live repository state and dirty-work scope?

**Answer:** The checkout is on `fix/ai-skills-online-followups-20260825` at
`4feeb37`. It has 228 uncommitted paths: 99 under `claude-skills`, 114 under
`codex-skills`, 9 under `skills-src`, 2 under `scripts`, 2 under `docs`, and 2
root files.

**Evidence:**
- `git rev-parse HEAD`, `git status --short` — live checkout probe on 2026-08-30.
- `git diff --stat` — 31 tracked files changed; additional untracked files are present.

**Implications:** The supplied handoff's recorded `2d27dd3` is stale. A lock
must not be promoted from this worktree until ownership is separated and the
source commit is clean.

### Q2: Which surfaces govern the Claude workflow?

**Answer:** `skills-src/manifest.json` governs generated versus
provider-owned skills. The Claude install manifest selects portable skills.
The Claude `review-controller` source includes a worker under the skill tree,
but instructs operators to copy that worker separately to `~/.claude/agents/`.
The installer copies only manifest-listed skill directories.

**Evidence:**
- `skills-src/manifest.json:2,21-29` — generated/provider-owned distinction and declared fork.
- `claude-skills/package/install-manifest.json:10-20` — `review-controller` is absent from Claude optional skills.
- `claude-skills/skills/review-controller/SKILL.md:16-22` — worker placement and output contract.
- `scripts/Install-AgentSkills.ps1:206-237,334-336,382-389` — manifest-driven skill-directory copying.
- `codex-skills/local-hooks/devhome-lifecycle/README.md:3-16,32-47` — Handoff Relay source and projection ownership.

**Implications:** The live Claude review-controller works only because the
runtime copies were installed separately. A clean Claude package export/install
does not reproduce the complete workflow.

### Q3: What validation evidence is current?

**Answer:** Provider generation, declared-fork parity, README counts, and
whitespace checks pass. Strict ready-package validation fails on seven
unmanifested Claude directories, including `review-controller`. The live
read-only environment observer returns `ACCEPTANCE_FAILED`, with promotion and
repair both false.

**Evidence:**
- `Build-ProviderSkillPackages.ps1 -Check` — PASS, 47 files across 16 skills.
- `Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork` — PASS, 16 generated pairs and 2 declared forks.
- `Update-ReadmePackageCounts.ps1 -Check` — PASS.
- `Test-ReadyPackages.ps1 -StrictSkillManifest -SkipExportSmoke -SkipInstallerSmoke` — FAIL: `cc-workflow-builder`, `chief-operator`, `codebase-design`, `docs-clean`, `resolving-merge-conflicts`, `review-controller`, `verify`.
- `git diff --check` — exit 0; output contains only line-ending warnings.
- `Get-AiEnvironmentState` — `ACCEPTANCE_FAILED`; failed `remember-posttooluse`; candidate lock; source commit and payload mismatches; Claude `2.1.251` is not tested in the lock (`2.1.243`).
- SHA-256 probe — repo, `C:\Users\Sev\.claude`, and `D:\DevHome\state\claude` review-controller skill and worker copies match.

**Implications:** Historical passing reports do not establish current
promotion readiness because the source commit, lock, provider version, and
worktree have changed or remain unaccepted.

### Q4: Where can durability fail?

**Answer:** There are four confirmed gaps:

- Package reproducibility: Claude's manifest omits `review-controller`, and the
  worker's global-agent placement is outside the portable installer contract.
- Evidence freshness: the Claude skill freezes locations but does not record
  content hashes or re-read every artifact before acceptance (`SKILL.md:36,63-66,89-97`).
- Acceptance/projection: the lock is `candidate`, its Remember gate is `FAIL`,
  and the observer reports Claude hook projection and payload mismatches
  (`scripts/AiEnvironment/locks/snd-desk.lock.json:4-9,58-64`).
- Runtime placement: the adapter still derives generated state from ambient
  `CODEX_HOME`, so the no-AppData lifecycle guarantee is incomplete
  (`codex-skills/local-hooks/devhome-lifecycle/README.md:8-12`).

### Q5: What is the smallest repeatable durability gate?

**Answer:** A durable release requires all of the following in one clean,
owned change:

1. Put `review-controller` in the Claude package manifest and make the worker
   placement explicit and installer-tested.
2. Add mechanical tests for package export/install completeness and repo-to-
   runtime SHA-256 convergence.
3. Re-read and re-hash every captured review artifact at each freshness gate;
   reject stale evidence.
4. Capture a new lock from the clean commit, test the observed Claude version,
   reconcile the source/projection payloads, and pass `remember-posttooluse`.
5. Run the ready-package, parity, focused tests, and clean-worktree checks;
   only then promote the lock in a separate reviewed change.

**Evidence:**
- `scripts/AiEnvironment/README.md:33-48` — candidate-lock and clean-commit promotion contract.
- `codex-skills/local-hooks/devhome-lifecycle/README.md:163-181,195-204` — Claude refresh/drift checks and separate Remember acceptance.
- `scripts/Test-ReadyPackages.ps1:405-443` — manifest completeness gate.

## Cross-Cutting Analysis

### Constraints

- Claude and Codex `review-controller` are intentionally provider-owned forks;
  they cannot be generated from one shared skill document.
- The current checkout mixes unrelated Claude, Codex, hook, environment-lock,
  and usage-stat changes, so selective ownership is required.
- The live Remember acceptance is host-dependent and currently fails by timeout.

### Risks

| Risk | Likelihood | Impact | Notes |
|---|---|---|---|
| Clean Claude install omits review-controller | High | High | Manifest does not list it. |
| Review cites changed evidence as frozen | Medium | High | No content fingerprint is required by the Claude contract. |
| Lock promotion records untested or mismatched runtime | High | High | Observer currently reports candidate, dirty, mismatched, and untested state. |

### Open Questions

- Actual end-to-end Claude specialist execution was not run in this read-only
  discovery; only source, package, hashes, gates, and environment observation
  were checked.

## Recommendation

Findings support proceeding with a narrowly owned package-and-acceptance plan.
Resolve Claude manifest/worker packaging and the Remember/lock gates before any
runtime promotion or deployment.
