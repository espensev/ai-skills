# Review - DevHome Lifecycle Plugin And Synchronization

**Date:** 2026-08-16
**Surface:** fixed point `1036ee8...HEAD` (`70a6c92`, `ed97d29`)
**Spec source:** current user requests to keep the lifecycle package synchronized as an AI Skills plugin choice and keep its state out of AppData
**Standards sources:** `AGENTS.md`, `CLAUDE.md`, `codex-skills/AGENTS.md`, shared `common_dev/AGENTS.md`, and OpenAI's plugin packaging documentation
**Verdict:** FAIL

## Findings

### High

- [axis: regression] Remember capture fails against the supported installed
  plugin within the production PostToolUse timeout.
  Evidence: `Invoke-RememberAdapter.py:31-35,495-499` applies a three-second
  PostToolUse/Stop upstream bound, and `:693-696` converts a timeout to neutral
  `{}`. The installed-plugin case at `tests/test_remember_adapter.py:759-818`
  reproducibly exceeds that bound. An independent in-process probe with only
  the timeout raised to ten seconds completed the same case in 4.011 seconds.
  Impact: Codex receives a fail-open result but the expected Remember capture
  markers are omitted, so the feature's core PostToolUse synchronization is not
  currently reliable.
  Recommendation: establish a measured supported execution budget, align the
  adapter and outer hook deadlines in `hooks.json`, and lock the installed-plugin
  case green before live acceptance.

### Medium

- [axis: regression] the PreToolUse generated-memory guard can be bypassed by a
  shell redirection with no whitespace after `>`.
  Evidence: `Invoke-DevHomeHook.ps1:31` recognizes redirection only when `>` is
  followed by whitespace or end-of-command. Feeding
  `echo blocked > D:\DevHome\state\codex\memories\MEMORY.md` to the hook returns
  `permissionDecision=deny`, while the semantically equivalent
  `echo bypass>D:\DevHome\state\codex\memories\MEMORY.md` returns `{}`. The
  commands were supplied as hook input and were not executed.
  Impact: a direct shell write to generated native memory can pass the stated
  safety guard, violating the repository's memory-authority contract.
  Recommendation: fix token-aware redirection detection and add regression
  cases for no-space `>`, `>>`, descriptor redirection, quoted paths, and both
  PowerShell and cmd/Bash-compatible forms.

- [axis: spec] the plugin is installed and enabled, but its SessionStart
  reconciler is not trusted, so automatic source-to-runtime upkeep is not active.
  Evidence: `codex plugin list --json --available` reports
  `devhome-lifecycle@ai-skills` version `0.1.0` with `installed=true` and
  `enabled=true`; `D:\DevHome\state\codex\config.toml:1060` begins the current
  `[hooks.state]` table, but that table has no
  `devhome-lifecycle@ai-skills:hooks/...` record. OpenAI documents that installing
  or enabling a plugin does not trust its hooks automatically:
  <https://developers.openai.com/plugins/build/plugins>.
  Impact: cache and runtime checks can both report `CURRENT` while Codex still
  skips the plugin's startup reconciler.
  Recommendation: restart Codex, inspect and explicitly trust the exact
  SessionStart command in `/hooks`, then run one attended new-session smoke.

- [axis: regression] the source-only release gate cannot detect the installed
  Remember regression above.
  Evidence: `scripts/Test-ReleaseReadiness.ps1:38-55` runs provider contracts
  and the two isolated lifecycle Pester files but not
  `tests/test_remember_adapter.py`. A direct run of that 74-test suite produced
  installed/warm-hook timeouts and a fail-open `{}` result; a sequential rerun
  passed 73/74 and left only the installed PostToolUse case red.
  Impact: a green package gate proves catalog, cache, installer, and projection
  contracts, but does not currently prove live Remember compatibility. The
  failing live behavior above.
  Recommendation: split hermetic adapter coverage from installed-plugin
  integration, run the hermetic subset in the normal gate, and add an explicit
  target-machine lifecycle acceptance switch for the installed integration.

- [axis: spec] the Remember adapter's generated state still follows ambient
  `CODEX_HOME`, so the no-AppData placement requirement is not complete.
  Evidence: `Invoke-RememberAdapter.py:647-653` reads `CODEX_HOME` and passes it
  to `AdapterLayout.for_home`; `:92-100` then places mirrors, checkpoints,
  locks, and logs beneath `<CODEX_HOME>\remember-adapter`. A read-only layout
  probe with `CODEX_HOME=C:\Users\Sev\AppData\Local\Codex` resolves the adapter
  root to `C:\Users\Sev\AppData\Local\Codex\remember-adapter`.
  Impact: plugin registration, cache, and the five runtime files stay on D, but
  lifecycle-generated adapter state can still be redirected into AppData and
  Remember discovery/transcript validation can follow the wrong Codex root.
  Recommendation: pin production adapter state and session/plugin discovery to
  the physical DevHome Codex root, with an explicitly named test-only override
  for fixtures, then add an ambient-AppData regression test.

### Low

- [axis: regression] plugin synchronization output does not expose enabled or
  trust-review state.
  Evidence: `Sync-DevHomeLifecyclePlugin.ps1:450-467` reports cache/install
  convergence fields but omits the installed record's `enabled` value and any
  `TrustReviewRequired` or `RestartRequired` guidance.
  Impact: operators can reasonably misread `Status=CURRENT` as active startup
  reconciliation.
  Recommendation: add activation-state fields and a clear `/hooks` next action
  without auto-editing enablement or trust.

- [axis: spec] the unrelated `wt-local` marketplace remains sourced from
  Intelligent Terminal's AppData staging area.
  Evidence: the active Codex configuration and plugin list still identify
  `wt-agent-hooks@wt-local` separately from `devhome-lifecycle@ai-skills`.
  Impact: this is a second, independently owned AppData surface in addition to
  the lifecycle adapter-state blocker above.
  Recommendation: review that integration separately with its owner; do not
  move or delete its generated staging state as part of this feature.

## Verification

- legacy and DevMesh v2 machine identity checks - pass; verified controller
  `snd-desk`, installation `ca96d510-7d87-4cec-8e1a-bd8fc3866903`.
- `Install-AgentSkills.ps1 -Provider Codex -CodexLocalPlugin DevHomeLifecycle`
  after documentation freeze - pass; plugin action `REFRESHED` on verified
  `snd-desk`.
- immediate `Sync-DevHomeLifecyclePlugin.ps1 -Check` - pass; `CURRENT`, action
  `NONE`, 11/11 source-cache hashes match.
- `Sync-DevHomeCodexHooks.ps1 -Check` - pass; `CURRENT`, five files.
- `codex plugin marketplace list --json` - pass; `ai-skills` resolves to the
  canonical D-drive checkout.
- `codex plugin list --json --available` - pass; plugin installed and enabled at
  version `0.1.0`.
- lifecycle Pester contracts - pass in the current feature gate, 39/39.
- standalone Remember adapter unittest suite - fail; host-dependent integration
  initially produced six load-sensitive errors/failures; a sequential rerun
  passed 73/74 and left the installed PostToolUse timeout reproducibly red.
- narrowed installed PostToolUse integration test - fail; reproducible
  three-second upstream timeout.
- narrowed 20-process benchmark entry-point test - pass; 20.917s.
- generated-memory redirection guard probe - fail; spaced `>` denied but
  no-space `>` returned neutral `{}`.
- ambient-AppData adapter layout probe - fail; generated root followed
  `CODEX_HOME` into AppData.
- `scripts/Test-ReleaseReadiness.ps1` after documentation synchronization -
  pass; 28 Python contracts and 39/39 lifecycle Pester tests.
- `git diff --check 1036ee8...HEAD` and both commit checks - pass.

## Coverage Notes

- Files reviewed deeply: `.agents/plugins/marketplace.json`, `README.md`,
  `scripts/Install-AgentSkills.ps1`, `scripts/Test-ReleaseReadiness.ps1`, both
  plugin/runtime synchronizers, the direct installer, both hook manifests, the
  plugin manifest, the bundled operator skill, both Pester suites,
  `test_local_plugin_contract.py`, and all lifecycle operator/release/discovery
  documentation.
- Files sampled around their security, process-containment, transcript, and
  live-integration seams: `hooks.json`, `hooks/Invoke-DevHomeHook.ps1`,
  `hooks/Invoke-RememberAdapter.cmd`, `hooks/Invoke-RememberAdapter.py`,
  `hooks/Invoke-RememberClaude.cmd`, and `tests/test_remember_adapter.py`.
- The complete two-commit name-status surface contained 25 files; every file is
  represented in the deep or sampled groups above.
- Excluded as unrelated user-owned work: deleted
  `docs/reviews/review-2026-06-25-gemini-adapter-crosspoll.md`.

## Open Questions

- Does the installed Remember `0.20.0` PostToolUse hook now require a larger
  bounded timeout, or is it blocked on another nested dependency?
- Which adapter cases are hermetic enough for the default release gate, and
  which should remain behind an explicit live-host switch?
- Should `wt-local` be migrated off AppData in a separate Intelligent Terminal
  ownership review?
