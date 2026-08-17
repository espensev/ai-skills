# Review - DevHome Lifecycle Plugin Placement

**Date:** 2026-08-16
**Surface:** working tree
**Spec source:** current user request: keep the lifecycle plugin out of AppData and use the local DevHome system root
**Standards sources:** `AGENTS.md`, `codex-skills/AGENTS.md`, `CLAUDE.md`, shared `common_dev/AGENTS.md`
**Verdict:** FAIL

**Scope note:** the initial control-plane review covered marketplace, cache, and
runtime-file placement but missed adapter-generated state. The follow-up
[full feature review](review-2026-08-16-devhome-lifecycle-feature.md) found the
remaining AppData relocation path and supersedes the earlier pass.

## Findings

### High

No findings.

### Medium

- [axis: spec] adapter-generated lifecycle state is not pinned to the physical
  DevHome root.
  Evidence: `Invoke-RememberAdapter.py:647-653` derives its layout from ambient
  `CODEX_HOME`, while `:92-100` places mirrors, checkpoints, locks, and logs
  under `<CODEX_HOME>\remember-adapter`. A read-only AppData-like layout probe
  resolved to `C:\Users\Sev\AppData\Local\Codex\remember-adapter`.
  Impact: marketplace configuration, plugin cache, and the five installed hook
  files are correctly on D, but the broader requirement that lifecycle state
  stay out of AppData is not yet met.
  Recommendation: pin production adapter state, Remember discovery, and session
  validation to `D:\DevHome\state\codex`, retaining only an explicit test-only
  alternate-root seam.

### Low

- [axis: spec] the active Codex configuration contains a separate legacy marketplace, `wt-local`, whose source is Intelligent Terminal's AppData staging directory.
  Evidence: `D:\DevHome\state\codex\config.toml:299-302` points `wt-local` at `C:\Users\Sev\AppData\Local\Packages\Microsoft.IntelligentTerminal_8wekyb3d8bbwe\LocalState\IntelligentTerminal\hook-bundle-staging\codex`; `codex plugin list --json --available` reports `wt-agent-hooks@wt-local` installed and enabled. The new `devhome-lifecycle@ai-skills` code and registration do not depend on it.
  Impact: this independently keeps a machine-wide no-AppData plugin policy
  unmet; the lifecycle package also has the separate adapter-state blocker
  above.
  Recommendation: treat migration or removal of `wt-local` as a separate change because it is owned by the Intelligent Terminal integration and has trusted hook state.

## Verification

- `codex plugin marketplace list --json` - pass; `ai-skills` resolves to `D:\Development\AI-related\Ai-Skills`.
- `codex plugin list --json --available` - pass; `devhome-lifecycle@ai-skills` is installed and enabled from the repository source.
- `Sync-DevHomeLifecyclePlugin.ps1 -CodexHome D:\DevHome\state\codex -Check` - pass; status `CURRENT`, 11 hashed files, no drift.
- `Get-Item D:\DevHome\state\codex` and cache/config children - pass; physical directories/files with no link target.
- `Get-Item C:\Users\Sev\.codex` - pass; this user-profile path is a junction to `D:\DevHome\state\codex`, not duplicate storage.
- scoped AppData and user-root search for `devhome-lifecycle`/`ai-skills` - pass; no lifecycle payload exists in Intelligent Terminal AppData. Matches under `C:\Users\Sev\.codex` resolve through the DevHome junction.
- ambient AppData-like `CODEX_HOME` control-plane tests - pass; plugin CLI/cache
  and startup reconciliation still select `D:\DevHome\state\codex`.
- ambient AppData-like adapter-layout probe - fail; generated adapter state
  still follows `CODEX_HOME`.
- `Install-DevHomeCodexHooks.ps1 -TargetRoot C:\Users\Sev\AppData\Local\Codex -Check` - pass; refused before drift evaluation, identity verification, or writes.
- production call-site scan for `AllowTestOnly*` - pass; overrides appear only in their declarations and isolated test fixtures.
- `scripts/Test-ReleaseReadiness.ps1` - pass; 28 Python contracts and 39 lifecycle Pester tests passed.
- live source/cache/runtime convergence - pass; 11 plugin payload hashes match, five runtime files are current, and the second plugin sync reports `Action=NONE`, `Changed=False`.

## Coverage Notes

- Files reviewed deeply: `.agents/plugins/marketplace.json`, `README.md`, the direct installer, both plugin synchronizers, plugin and hook manifests, bundled skill, `scripts/Install-AgentSkills.ps1`, package README, local-access and release-readiness docs, discovery report, release gate, and all new/modified plugin contract tests.
- Files reviewed for placement-sensitive assertions: `DevHome-Hooks.Tests.ps1`, `DevHome-PluginSync.Tests.ps1`, and `test_local_plugin_contract.py`.
- Excluded as unrelated user-owned work: deleted `docs/reviews/review-2026-06-25-gemini-adapter-crosspoll.md`.
- Follow-up review inspected the runtime adapter's path derivation and found the
  missed generated-state placement issue above.

## Open Questions

- Whether the independent `wt-local` Intelligent Terminal plugin should be migrated off AppData is outside the lifecycle-plugin placement fix and needs its own ownership-aware review.
- Whether adapter state should share `D:\DevHome\state\codex\remember-adapter`
  directly or a dedicated D-drive state subroot should be decided during the
  focused fix; either choice must be explicit and testable.
