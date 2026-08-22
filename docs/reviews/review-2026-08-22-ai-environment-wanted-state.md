# Review - AI Environment Wanted-State Maintenance

**Date:** 2026-08-22
**Surface:** current Ai-Skills source tree plus the installed Codex and Claude
DevHome projections on verified controller `snd-desk`
**Spec source:** user request to make hooks, skills, plugins, and agent upgrades
maintainable as an evolving wanted state
**Standards sources:** `AGENTS.md`, `CLAUDE.md`, the shared machine-context
`AGENTS.md`, `codex-skills/local-hooks/devhome-lifecycle/README.md`, current
OpenAI Codex hooks/skills documentation, and current Claude Code
hooks/skills/plugins documentation
**Verdict:** FAIL

## Findings

### High

- [axis: regression] The live lifecycle source authority has no recoverable
  repository identity, while SessionStart can still promote that mutable source
  into the installed hook projection.
  Evidence: `git -C D:\Development\AI-related\Ai-Skills rev-parse
  --show-toplevel` reports that the directory is not a Git repository, although
  `AGENTS.md:23-32` declares its provider packages and lifecycle directory to be
  canonical source authorities. The plugin hook embeds that checkout directly
  as `-SourcePackageRoot` (`hooks/hooks.json:10-11`), and the synchronizer then
  invokes the source installer when it observes drift
  (`Sync-DevHomeCodexHooks.ps1:58-107`). The public remote still has `main` at
  `5881f07d948e162e94b4a92d2a07a2cb7182220e`, but no local commit proves how
  this tree relates to it.
  Impact: source edits can become runtime candidates without a reviewable
  commit, clean-tree gate, accepted artifact digest, or dependable rollback.
  Recommendation: restore Git provenance first, then make SessionStart reconcile
  only to a separately accepted lock/artifact. A working checkout must never be
  the automatic promotion source.

- [axis: regression] Remember PostToolUse capture is still not accepted against
  the installed `remember@0.20.0` plugin.
  Evidence: the current 74-test adapter suite passes 73 tests and errors in
  `test_installed_post_tool_hook_bootstraps_capture_markers` after the installed
  `post-tool-hook.sh` exceeds the adapter's three-second bound. The adapter
  converts runtime failures to a neutral hook result, so the agent can continue
  while capture is absent. This is the same open behavior recorded in
  `review-2026-08-16-devhome-lifecycle-feature.md:14-27`.
  Impact: green source/cache/runtime checks do not prove that session memory is
  being captured.
  Recommendation: keep live lifecycle acceptance red until a measured timeout
  budget or decoupled queue/worker makes the installed integration reliable.

### Medium

- [axis: spec] There is no single wanted-state model for the effective AI
  environment; existing manifests govern packages, not activation or
  acceptance.
  Evidence: `skills-src/manifest.json` governs shared-skill authorship,
  provider install manifests govern copied files, `Sync-DevHomeLifecyclePlugin.ps1`
  separately hard-codes a core payload at line 41, the Codex and Claude hook
  installers each own different runtime fragments, and provider settings hold
  activation state. `Compare-AgentSkillRoots.ps1 -Provider Both
  -FailOnMissingOrStale` passes even though the Codex plugin command is broken,
  seven disabled skill paths no longer exist, and Remember acceptance is red.
  Impact: several individually green checks can describe an unusable or
  partially active environment.
  Recommendation: introduce one cross-provider deep module with the external
  interface `Get`, `Plan`, `Apply`, and `Verify`; keep provider-specific files,
  trust, and settings behind Codex and Claude adapters.

- [axis: regression] One stale, disabled, foreign marketplace prevents the
  lifecycle plugin checker from observing its own plugin.
  Evidence: `D:\DevHome\state\codex\config.toml:361-364` registers `wt-local`
  at an IntelligentTerminal staging directory that no longer exists, while
  `:421-422` disables its plugin. Codex 0.149.0 still fails both
  `plugin marketplace list --json` and `plugin list --json --available` before
  `Sync-DevHomeLifecyclePlugin.ps1 -Check` can classify
  `devhome-lifecycle@ai-skills`. An independent closed-payload comparison shows
  the lifecycle `0.2.0` cache itself remains hash-current at 13/13 files.
  Impact: unrelated control-plane debris blocks maintenance and obscures the
  difference between owned drift and foreign degradation.
  Recommendation: make the observer resilient: statically inspect the owned
  registry/cache when global enumeration fails, report
  `DEGRADED_FOREIGN_MARKETPLACE`, and never delete the foreign registration
  without its owner's explicit migration decision.

- [axis: regression] Skill installation and activation still depend on legacy
  locations and a large path-specific suppression list.
  Evidence: the Codex installer and comparator target `$HOME\.codex\skills`
  (`Install-AgentSkills.ps1:145-159`,
  `Compare-AgentSkillRoots.ps1:78-87`), while current Codex documentation names
  `$HOME/.agents/skills` as the user skill root. The active Codex config contains
  180 disabled `skills.config` entries and seven paths that no longer exist.
  Claude expresses a smaller capability policy through `skillOverrides`, but
  the two providers are not generated from one intent set.
  Impact: provider changes, retired skills, and moved roots accumulate manual
  tombstones; file parity does not prove which skills the model can actually
  discover or invoke.
  Recommendation: declare logical enabled/disabled capability sets once,
  render provider-native activation policy, and migrate custom Codex skills to
  `.agents/skills` after a fresh-session shadow comparison. Preserve `.codex`
  only for system/legacy content that is still required.

- [axis: regression] Both the Handoff Relay and Remember bridge depend on
  provider transcript internals without an explicit compatibility gate.
  Evidence: `Invoke-HandoffRelay.ps1:65-130,237-250` parses JSONL transcript
  records to recover developer/system instructions, and
  `Invoke-RememberAdapter.py:738-986` mirrors and translates transcript records.
  Current Codex documentation explicitly says `transcript_path` is convenient
  but its transcript format is not a stable hook interface.
  Impact: a Codex update can silently turn the fail-open relay or capture bridge
  into a no-op while hook/config drift checks remain green.
  Recommendation: make cwd-to-project mapping the primary relay target source,
  keep transcript parsing as a versioned adapter, and mark an unseen provider
  version `UNTESTED` until recorded fixture and live smoke contracts pass.

### Low

- [axis: spec] Status vocabulary is too narrow for the actual operator gates.
  Evidence: lifecycle checks mostly return `CURRENT`, `UNCHANGED`, `INSTALLED`,
  `MISSING`, `STALE`, or `CONFLICT`; plugin status omits effective trust and
  acceptance even though current Codex trust is hash-scoped and changed hooks
  require manual review.
  Impact: `CURRENT` can be mistaken for active, trusted, and behaviorally
  accepted.
  Recommendation: report independent lanes: `source`, `artifact`, `projection`,
  `activation`, `trust`, `compatibility`, and `acceptance`, then calculate the
  top-level state from those lanes.

## Verified Current State

- Controller identity: `snd-desk`, installation
  `ca96d510-7d87-4cec-8e1a-bd8fc3866903`, verified through both compatibility
  and DevMesh v2 verifiers before this report was written.
- Provider versions: Codex CLI `0.149.0`; Claude Code `2.1.239`.
- Codex six-file hook projection: `CURRENT`.
- Claude two-file Handoff Relay projection: `CURRENT`.
- Lifecycle plugin cache: source and cache match for `0.2.0`, 13/13 files;
  global CLI convergence check is blocked by `wt-local`.
- Codex activation/trust: `devhome-lifecycle@ai-skills` is enabled and the
  SessionStart hook has a persisted trust hash, so the prior handoff's trust
  gate is stale.
- Portable skills: installed Codex and Claude roots match manifest-listed
  files.
- Package gates: ready-package validation, README counts, 44-file provider
  generation, and provider-fork enforcement pass. Release readiness still
  fails at Git diff checks because the source has no `.git` metadata.
- Lifecycle contracts: Pester 49/49 pass. Installed Remember integration:
  73/74 pass with one timeout error.

## Recommended Target Architecture

Keep three records separate:

1. **Intent** - a reviewed `profiles/snd-desk.json` declaring logical
   capabilities, ownership, paths, enablement policy, trust requirements, and
   acceptance gates. It should not contain secrets or provider-generated trust
   hashes.
2. **Accepted lock** - an immutable `locks/snd-desk.lock.json` resolving intent
   to a source commit, provider versions last tested, plugin versions, payload
   inventory, and SHA-256 digests. Updating this lock is the promotion event.
3. **Observed state** - a generated report under
   `D:\DevHome\state\ai-environment`, never a source authority, containing
   effective provider state and reason-coded drift.

The external interface should stay small:

```text
Get-AiEnvironmentState     observe without mutation
New-AiEnvironmentPlan     compare intent + lock + observed state
Invoke-AiEnvironmentApply apply only an approved, locked plan
Test-AiEnvironment        verify projection + activation + trust + acceptance
```

Codex and Claude adapters belong behind that seam. They translate logical
resources such as `skill:review`, `hook:handoff-relay`, and
`plugin:devhome-lifecycle` into provider-native roots, settings, marketplace
records, trust observations, and fresh-session smoke checks. The existing
lifecycle scripts become payload/install implementations called by the adapter,
not competing top-level control planes.

Each resource needs an ownership mode:

- `managed` - exact convergence is allowed from the accepted lock;
- `observed` - health is reported but unrelated settings are preserved;
- `forbidden` - a known unsafe/stale resource blocks promotion;
- `manual-gate` - trust, attended UI review, or operator acceptance is required.

Recommended top-level states are `CURRENT`, `DRIFTED`, `PENDING_TRUST`,
`UNTESTED_PROVIDER_VERSION`, `SOURCE_UNTRUSTED`,
`DEGRADED_FOREIGN_MARKETPLACE`, and `ACCEPTANCE_FAILED`.

## Upgrade Workflow

1. Acquire provider and Ai-Skills updates into a clean, identified worktree.
2. Detect provider-version or schema changes and render a candidate lock.
3. Build a staging bundle; never reconcile a mutable checkout directly.
4. Run manifest/parity tests, provider fixture tests, and isolated home/config
   smoke checks.
5. Produce a reviewable plan separating source, runtime, activation, trust, and
   acceptance changes.
6. After approval, back up and atomically apply only managed resources.
7. Start fresh Codex and Claude sessions; review changed hooks and run visible
   acceptance checks.
8. Promote the lock only after those checks pass. Rollback reapplies the prior
   locked bundle; it does not reconstruct files from ad hoc backups.

Provider applications may continue to auto-update, but an unseen version must
not silently become "supported." It should keep the last accepted hook/skill
bundle, run compatibility checks, and report `UNTESTED_PROVIDER_VERSION` until
the new version passes.

## Implementation Order

1. Recover Git provenance without replacing the current tree; compare it to
   remote `main` and preserve unpushed work.
2. Add the read-only intent/lock/observer module and generate a report matching
   today's known state. Do not mutate provider config in this phase.
3. Fix the `wt-local` ownership decision or make foreign marketplace failure
   non-blocking for owned observation.
4. Pin Remember state/plugin discovery to physical DevHome and resolve the
   installed PostToolUse timeout before declaring lifecycle acceptance.
5. Switch SessionStart from working-tree promotion to last-known-good locked
   artifact repair.
6. Generate Codex and Claude skill activation from one capability policy and
   stage the Codex `.agents/skills` migration.
7. Add provider-version fixture snapshots and an attended fresh-session
   acceptance gate.

## Verification

- `Sync-DevHomeCodexHooks.ps1 -Check` - pass, 6 files current.
- `Install-DevHomeClaudeHandoffRelay.ps1 -Check` - pass, 2 files current.
- `Sync-DevHomeLifecyclePlugin.ps1 -Check` - fail before owned-state
  classification because `wt-local` has no supported manifest.
- independent lifecycle source/cache SHA-256 comparison - pass, 13/13 files.
- `Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale` - pass.
- lifecycle Pester suites - pass, 49/49.
- Remember adapter unittest suite - fail, 73/74; installed PostToolUse timeout.
- `Test-ReleaseReadiness.ps1 -SkipUnitTests` - package/parity portions pass;
  Git diff gate fails because the source tree is not a worktree.
- `git ls-remote --symref https://github.com/espensev/ai-skills.git ...` - pass;
  remote `main` resolves to `5881f07d...`, without proving local lineage.

## Coverage Notes

- Deep-reviewed: lifecycle README, both hook manifests, plugin manifest,
  Codex/Claude installers, Codex runtime synchronizer, plugin synchronizer,
  Handoff Relay, package installer/comparator, provider and source manifests,
  repository standards, live Codex config summary, and live Claude settings
  summary.
- Behaviorally verified: source/runtime convergence, cache hashes, provider
  versions, activation/trust records, package gates, lifecycle contracts, and
  the installed Remember integration.
- Excluded: mutation of Codex/Claude settings, marketplace cleanup, plugin
  reinstall, hook trust changes, provider upgrades, and source-provenance
  recovery.

## Open Questions

- Which system owns `wt-local`: IntelligentTerminal, a DevHome profile module,
  or an obsolete experiment? That ownership decision is required before
  removal or relocation.
- Should provider applications auto-update with a compatibility hold, or should
  the profile pin explicit application channels as well as extension payloads?
- Is Remember's installed PostToolUse latency an acceptable bounded timeout
  increase, or should capture be decoupled from the hook into a local queue?

## Phase 1 implementation update

Implemented the recommended read-only seam on 2026-08-22:

- Restored root Git metadata at verified remote base
  `5881f07d948e162e94b4a92d2a07a2cb7182220e` on recovery branch
  `recovery/ai-environment-wanted-state-20260822` without replacing or resetting
  working-tree files; pre-existing local edits and deletions remain visible.
- Added `scripts/AiEnvironment` with JSON Schema contracts, the `snd-desk`
  profile, an explicitly candidate lock, private Codex/Claude adapters, and the
  public read-only interface `Get-AiEnvironmentState`,
  `New-AiEnvironmentPlan`, and `Test-AiEnvironment`.
- Added 30 black-box Pester contracts, including a fully current fixture,
  managed and foreign marketplace failures, provider-version and command
  timeout handling, exact hook-trust hash validation, Claude registry
  correlation, lock payload contracts, deterministic planning, strict nested
  state schemas, source and acceptance gates, plus proof that Get/Plan/Test do
  not mutate observed roots.
- Closed all seven findings from an independent adversarial review: managed
  predicates now require explicit truth, TOML inline comments are tokenized,
  missing registries and empty locks fail closed, provider processes have a
  bounded process-tree timeout, and foreign-owner actions are routed explicitly.
- A follow-up adversarial pass found and closed one additional gap: profile and
  lock JSON Schemas are now enforced before any provider command runs, and the
  normalized state is validated before it is returned.
- A pre-ship audit found and closed two more fail-open paths: resource shapes
  without provider adapters are rejected, and candidate payloads/plugin versions
  must match raw blobs at the declared commit. Dirty or incomplete lock coverage
  cannot become repair-ready.
- Generated the first schema-valid observation at
  `D:\DevHome\state\ai-environment\snd-desk.observed.json`. It reports
  `ACCEPTANCE_FAILED` with active source-untrusted, drift, and degraded foreign
  marketplace lanes. `PromotionReady` and `RepairReady` remain false.
- Added the new contract suite to `scripts/Test-ReleaseReadiness.ps1`. The full
  release gate covers 41 Python contracts, 49 lifecycle Pester contracts,
  three installer contracts, and 30 wanted-state contracts.

No Codex or Claude hook, skill, plugin, trust, marketplace, enablement, or
provider application state was changed by Phase 1.
