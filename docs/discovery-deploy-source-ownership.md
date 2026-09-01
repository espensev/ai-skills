# Discovery — Deploy Source Ownership

**Goal:** Determine whether Ai-Skills owns the configuration, agent skills, and
Codex plugin deployment, and whether the current Codex/Claude surfaces are
complete and deployable from this repository.
**Date:** 2026-08-30
**Status:** complete
**Recommended next:** Plan a narrow packaging and deployment-contract change;
do not deploy the current dirty checkout.

## Questions

1. What does this repository own as canonical source for skills, configuration,
   agent definitions, hooks, and plugins?
2. Which manifests and scripts actually deploy those surfaces?
3. Are the current Codex and Claude packages complete relative to their source
   trees?
4. Are the installed skill roots, plugin cache, and lifecycle projections
   converged with the current source?
5. Is the current checkout ready to be treated as a deployable release?

## Findings

### Q1: What is canonical source?

**Answer:** Yes, the repository has an explicit source-authority model, but it
does not make every provider-owned runtime setting repository-owned.

**Evidence:**

- `AGENTS.md:23-40` names `codex-skills/` and `claude-skills/` as canonical
  provider package sources, keeps `codex-skills/local-hooks/devhome-lifecycle/`
  as machine-local source authority, and defines `scripts/AiEnvironment/` as a
  read-only wanted-state observer.
- `README.md:9-11,216-235` defines release and install manifests, the
  `skills-src/` generated-skill canon, and the provider-parity gate.
- `.agents/plugins/marketplace.json:1-18` is the repository-local `ai-skills`
  marketplace catalog for `devhome-lifecycle`.
- `codex-skills/local-hooks/devhome-lifecycle/README.md:14-20,98-119`
  explicitly keeps the lifecycle plugin outside portable manifests while
  making this checkout the source for its local plugin and hook projections.

**Implications:** The intended model is “deploy from this repository,” with
portable packages, a separate local Codex plugin, and generated runtime
projections. Codex plugin enablement/hook trust and provider settings remain
user/provider-owned state (`docs/local-agent-skill-access.md:103-106`).

### Q2: Which manifests and scripts deploy it?

**Answer:** Portable deployment is manifest-driven, but agent definitions are
outside that contract.

**Evidence:**

- `release-manifest.json:2-20` exports only the ready `codex-skills` and
  `claude-skills` packages.
- `codex-skills/package/install-manifest.json:2-51` and
  `claude-skills/package/install-manifest.json:2-42` select skills, contract
  files, runtime files, and runtime directories.
- `scripts/export-ready-skill-packages.ps1:61-113` exports only release-listed
  packages and install-manifest-selected content.
- `scripts/Install-AgentSkills.ps1:320-389,420-446` copies only manifest-listed
  skills/support files and separately invokes the local plugin synchronizer.
- `claude-skills/agent-definitions/README.md:3-8,19-26` says provider-owned
  Claude agent definitions are authored source but are not generated.
  `claude-skills/skills/review-controller/SKILL.md:16-19` says its worker must
  be copied to `~/.claude/agents/` because the skill installer does not manage
  agent files.

**Implications:** The repository owns the source copies of the Claude agent
definitions, and the live copies are currently present, but there is no
manifest-driven install/check path for the general `agent-definitions/` tree.
The `review-controller` worker is only self-contained inside its skill export;
the separate global-agent placement is a deployment gap.

### Q3: Are the current packages complete?

**Answer:** Codex is internally manifest-complete for its current package;
Claude is not.

**Evidence:**

- Current manifests list 26 Codex skills plus one source-only skill, and 16
  Claude skills plus one source-only skill. The package directories currently
  contain 27 Codex skill directories and 24 Claude skill directories.
- `claude-skills/package/install-manifest.json:10-23` omits these seven
  directories that exist under `claude-skills/skills/`: `cc-workflow-builder`,
  `chief-operator`, `codebase-design`, `docs-clean`,
  `resolving-merge-conflicts`, `review-controller`, and `verify`.
- `scripts/Test-ReadyPackages.ps1:425-439` treats unlisted package skill
  directories as warnings normally but as failures under the release gate's
  `-StrictSkillManifest` mode.
- Current command result: `Test-ReadyPackages.ps1 -StrictSkillManifest
  -SkipExportSmoke -SkipInstallerSmoke` fails on exactly those seven Claude
  directories.
- Current command results: `Build-ProviderSkillPackages.ps1 -Check`,
  `Compare-ProviderSkillParity.ps1 -FailOnUndeclaredFork`, and
  `Update-ReadmePackageCounts.ps1 -Check` all pass. This proves generated
  source/package parity and count consistency, not release completeness.

**Implications:** The seven Claude directories are backed-up provider-owned
source from commit `2d27dd3`, not automatically portable content. The next
change must explicitly decide whether each is deployable and should be added to
the Claude manifest, or should be moved/classified as source-only reference
material. Adding them blindly would change the published package contract.

### Q4: Are installed roots and plugin cache converged?

**Answer:** No. The lifecycle runtime projections are current, but the
portable roots and local plugin cache are stale.

**Evidence:**

- `Compare-AgentSkillRoots.ps1 -Provider Both -FailOnMissingOrStale` reports 13
  blockers: Codex has `codex-state-cleanup` and
  `usage-stats/scripts/codex_usage_window.py` missing plus four stale files;
  Claude has seven stale files, including the changed browser-control,
  diagnosing-bugs, handoff, memory-management, and usage-stats surfaces.
- `Sync-DevHomeLifecyclePlugin.ps1 -Check` reports `Status=STALE`, with four
  differing cached files: `hooks/Invoke-HandoffRelay.ps1`,
  `hooks/Invoke-RememberAdapter.py`, `hooks/Invoke-RememberClaude.cmd`, and
  `skills/devhome-lifecycle/SKILL.md`. The marketplace is present and the
  plugin is installed at version `0.3.0`.
- `Sync-DevHomeCodexHooks.ps1 -Check` reports `CURRENT` for six lifecycle
  files, and `Install-DevHomeClaudeHandoffRelay.ps1 -Check` reports `CURRENT`
  for two Claude relay files. These checks do not establish portable-skill or
  plugin-cache convergence.
- `Install-AgentSkills.ps1 -Provider Both -CodexLocalPlugin DevHomeLifecycle
  -DryRun -Force` predicts a refresh of all 26 listed Codex skills, all 16
  listed Claude skills, their support files, and the stale plugin cache.

**Implications:** “Most files are updated” is true only for repository source
and some lifecycle projections. It is false as a deployment statement: the
installed environment does not yet match the current source.

### Q5: Is this checkout release-ready?

**Answer:** No.

**Evidence:**

- Current checkout: branch
  `fix/ai-skills-online-followups-20260825`, `HEAD=4feeb37`, with 229 changed
  or untracked paths.
- `Get-AiEnvironmentState` reports `Status=ACCEPTANCE_FAILED`,
  `PromotionReady=false`, and `RepairReady=false`. Active statuses are
  `ACCEPTANCE_FAILED`, `DRIFTED`, `SOURCE_UNTRUSTED`, and
  `UNTESTED_PROVIDER_VERSION`.
- The observer sees Codex `0.151.0` and Claude `2.1.251`, while the candidate
  lock records tested versions `0.149.1` and `2.1.243`
  (`scripts/AiEnvironment/locks/snd-desk.lock.json:4-17`). It also reports a
  candidate lock, dirty source, source/lock and installed-payload mismatches,
  failed `remember-posttooluse`, and incomplete shared-skill lock coverage.
- `codex-skills/tests/test_local_plugin_contract.py` passes 6 tests, but that
  is a source contract check; it does not prove cache convergence, activation,
  or hook trust.

**Implications:** The current source should not be promoted or used as an
accepted deployment artifact. The package set, agent-definition deployment,
plugin cache, provider-version evidence, Remember acceptance, and lock
promotion need separate gates.

## Cross-Cutting Analysis

### Constraints

- Preserve the current dirty worktree and separate the intended packaging,
  agent-definition, plugin-cache, and lock changes before committing.
- `devhome-lifecycle` is machine-local and must remain outside the portable
  release/install manifests.
- Plugin installation does not prove enablement or hook trust; those remain
  Codex-managed user decisions.
- A candidate lock cannot become accepted from a dirty source tree or from
  provider versions not exercised by the lock.

### Risks

| Risk | Likelihood | Impact | Notes |
|---|---|---|---|
| Clean Claude install omits intended provider skills | High | High | Seven directories are on disk but not in the install manifest. |
| Agent definitions drift after manual copy | Medium | High | Source exists, but the installer has no general agent-definition contract. |
| Codex runs stale plugin behavior | High | High | Plugin is installed but cache check reports four differences. |
| Lock promotion records untested runtime | High | High | Candidate lock, dirty source, provider-version mismatch, and failed acceptance remain. |

### Open Questions

- Should the seven backed-up Claude skills become portable optional skills, or
  remain repository-owned source-only/reference material?
- Should the root installer gain a separate Claude agent-definition manifest and
  hash/check/install path, including the `review-controller` worker?
- After the owned change is isolated and committed, which exact Codex and Claude
  provider versions and Remember acceptance result should be captured in the
  next lock?

## Recommendation

Findings support a narrow implementation plan: decide the deployable Claude
skill set, add an explicit agent-definition deployment contract if those files
are part of the owned installation, refresh the Codex/Claude roots and local
plugin from a clean committed source, then recapture provider-version and
Remember acceptance evidence before lock promotion. Do not run the mutating
installer against the current 229-path dirty checkout.
