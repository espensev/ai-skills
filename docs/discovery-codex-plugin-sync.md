# Discovery - Codex Plugin Sync

**Goal:** Keep the DevHome lifecycle package synchronized through an Ai-Skills
plugin choice without turning machine-local hooks into a portable default.
**Date:** 2026-08-16
**Status:** complete
**Document role:** pre-implementation discovery snapshot; absence and gate
statements below describe the state inspected before implementation.
**Outcome:** implemented by `ed97d29`; current operation is documented in
[`codex-skills/local-hooks/devhome-lifecycle/README.md`](../codex-skills/local-hooks/devhome-lifecycle/README.md).
**Follow-up status:** catalog/cache convergence works, but overall acceptance
has open adapter, guard, and activation findings in the
[full feature review](reviews/review-2026-08-16-devhome-lifecycle-feature.md).

---

## Questions

1. Where does this repository expose plugin and AI-skill choices?
2. Which catalog is authoritative for each choice?
3. How can the lifecycle package remain machine-local?
4. What updates the deployed hook projection today?
5. Which contracts must prevent catalog, cache, and runtime drift?

---

## Findings

### Q1: Where does this repository expose plugin and AI-skill choices?

**Answer (at discovery time):** Portable skills were selected by provider
install manifests. The repository had no tracked Codex marketplace, so
`devhome-lifecycle` could not appear in the plugin picker or contribute a
plugin-provided skill.

**Evidence:**

- `codex-skills/package/install-manifest.json:2-45` declares the default and
  optional portable Codex skills.
- `scripts/Install-AgentSkills.ps1:229-292` copies every default and optional
  skill into the selected installed roots.
- `codex-skills/local-hooks/devhome-lifecycle/README.md:3-9` deliberately keeps
  the machine-local package outside the portable manifests.
- A repository scan found no tracked `.agents/plugins/marketplace.json` or
  `.codex-plugin/plugin.json` before this discovery.

**Implications:**

- Add a separate repository marketplace rather than broadening the portable
  skill manifest.
- Bundle a narrowly described `devhome-lifecycle` skill with the local plugin.

### Q2: Which catalog is authoritative for each choice?

**Answer:** `package/install-manifest.json` remains authoritative for portable
provider installs. A new `.agents/plugins/marketplace.json` should be the
repository-owned catalog for local Codex plugin choices.

**Evidence:**

- `release-manifest.json:2-19` publishes only the two provider packages.
- The live `wt-local` precedent uses `.agents/plugins/marketplace.json`, a
  `.codex-plugin/plugin.json` manifest, and `${PLUGIN_ROOT}` hook commands.
- Current Codex CLI help exposes `plugin marketplace add`, `plugin add`,
  `plugin list`, and `plugin remove` as the supported management surface.
- OpenAI's current plugin packaging documentation defines repo marketplaces at
  `$REPO_ROOT/.agents/plugins/marketplace.json` and plugin manifests at
  `.codex-plugin/plugin.json`:
  <https://developers.openai.com/plugins/build/plugins>.

**Implications:**

- Name the marketplace `ai-skills` and point it at the existing source-only
  lifecycle package.
- Keep the plugin source inside the repository; Codex owns its installed cache.

### Q3: How can the lifecycle package remain machine-local?

**Answer:** The plugin should be available only from the local Ai-Skills
marketplace and remain absent from both portable manifests. Its only plugin
hook should reconcile the existing verified runtime projection. The five
behavior hooks must not also be registered as plugin hooks.

**Evidence:**

- `scripts/export-ready-skill-packages.ps1:73-113` exports manifest-selected
  package content; a local marketplace is outside that path.
- `D:\DevHome\state\codex\config.toml` currently loads user hooks and plugin
  hooks independently, so registering the same behavior in both places would
  execute it twice.
- OpenAI documents that enabled plugins may provide lifecycle hooks and receive
  `PLUGIN_ROOT` and `PLUGIN_DATA`, while hook trust remains user-reviewed:
  <https://developers.openai.com/plugins/build/plugins>.

**Implications:**

- Use one stable plugin `SessionStart` hook for reconciliation only.
- Continue to deploy the closed five-file behavior-hook set through the
  existing identity-gated installer.
- Do not generate or edit Codex hook-trust state.

### Q4: What updates the deployed hook projection today?

**Answer:** At discovery time, only `Install-DevHomeCodexHooks.ps1` updated it,
and invocation was manual. General Ai-Skills synchronization did not touch
lifecycle hooks.

**Evidence:**

- `Install-DevHomeCodexHooks.ps1:61-91` hashes the owned runtime files and
  `:139-212` implements check, backup, copy, and convergence behavior.
- `scripts/Install-AgentSkills.ps1:100-114` targets Codex skill directories,
  not `hooks.json` or the runtime `hooks/` directory.
- Read-only inspection found no scheduled task, startup entry, active Git hook,
  or external installer invocation for this package.

**Implications:**

- Add a quiet plugin startup reconciler that first runs `-Check` and invokes
  the existing installer only when drift exists.
- Preserve the installer's machine verifier and closed ownership boundary.
- Make the cached bootstrap delegate to the canonical source package so a stale
  plugin cache cannot deploy stale runtime files.
- Add explicit source-to-cache hash convergence through
  `Install-AgentSkills.ps1 -CodexLocalPlugin DevHomeLifecycle`; restarting Codex
  is not a cache-refresh contract.

### Q5: Which contracts must prevent catalog, cache, and runtime drift?

**Answer:** Tests must validate marketplace-to-plugin references, plugin
metadata, the bundled skill, the single reconciliation hook, portable-manifest
exclusion, source-to-cache convergence, and idempotent runtime convergence.

**Evidence:**

- `codex-skills/tests/test_skill_docs_contract.py` is already executed by the
  Codex package contract suite used by release readiness.
- `codex-skills/local-hooks/devhome-lifecycle/tests/DevHome-Hooks.Tests.ps1`
  already verifies hook behavior and source-to-runtime drift handling.
- `scripts/Test-ReleaseReadiness.ps1:30-50` runs package, README, unit, and
  parity gates but has no plugin-catalog-specific contract yet.

**Implications:**

- Extend the lifecycle Pester suite for the sync wrapper.
- Add a lightweight Codex package unit contract for the repository marketplace
  and local plugin shape so normal release readiness covers the catalog.
- Test missing, stale, current, wrong-marketplace, and wrong-machine plugin
  cache states with a fake Codex CLI.

---

## Cross-Cutting Analysis

### Constraints

- `devhome-lifecycle` remains specific to verified controller `snd-desk` and
  installation `ca96d510-7d87-4cec-8e1a-bd8fc3866903`.
- Its normal Codex config, cache, and runtime projection are pinned to
  `D:\DevHome\state\codex`; caller `CODEX_HOME` does not relocate them.
- The plugin cache is a projection; the Ai-Skills checkout remains source
  authority.
- Source acquisition and Git synchronization remain separate from plugin and
  runtime convergence. No updater may silently pull or clean this repository.
- Hook trust remains an explicit user decision.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Duplicate lifecycle execution | High without separation | High | Plugin registers reconciliation only. |
| Accidental portable export | Medium | High | Keep both portable manifests unchanged and test exclusion. |
| Stale local plugin cache | Medium | High | Hash-check and explicitly reinstall through the local sync entrypoint; cached bootstrap delegates to repository source. |
| Wrong-machine mutation | Low | High | Reuse the installed hash-bound identity verifier. |
| Hidden hook-trust mutation | Low | High | Never edit trust state; require `/hooks` review. |

### Open Questions

All questions answered.

---

## Historical Recommendation

Add an `ai-skills` repository marketplace, package `devhome-lifecycle` as a
local plugin with one reconciliation hook and one operator skill, preserve the
existing direct runtime projection, and gate the new catalog shape through the
normal Codex contract suite. Add a tested explicit cache-convergence path rather
than relying on restart refresh behavior. Register and install the local plugin
only after live machine identity verification.
